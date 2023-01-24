import asyncio
import shutil
import sys
import threading

from asyncio import Queue, Task
from collections import OrderedDict
from functools import lru_cache
from inspect import signature, isawaitable
from threading import Lock
from typing import Any, Callable, Optional
from weakref import WeakSet


class Cursor:
    def __init__(self, initial, limit):
        self.current = initial
        self.limit = limit

    def __iter__(self):
        return self

    def __next__(self):
        v = None
        if self.current < self.limit:
            v = self.current
            self.current += 1
        else:
            v = 0
            self.current = v
        return v

    def __int__(self):
        return self.current


class TextMessageWithSpinner:
    is_animatable = True

    def __init__(self, msg: str, done):
        self.msg = msg.strip("\n")
        self._msg_done = done

        self._done = False

        self.animated = True
        self.spinners = ["/", "-", "\\", "-"]
        self.spinner_cursor = Cursor(0, 4)
        self.height = 1
        self.current_mark = "."

        self.content = f"{self.current_mark} {self.msg}"

    def __len__(self):
        return len(self.content)

    def wrap(self, width, height = None):
        if width < len(self.current_mark) + 1 + len(self.msg):
            content_part_begin = 0
            msg_width = width - 1 - len(self.current_mark)
            
            spaces = " " * (len(self.current_mark) + 1)
            parts = []

            while content_part_begin < len(self.msg) - msg_width:
                parts.append(spaces
                             + self.msg[content_part_begin:content_part_begin
                                                           + msg_width])
                content_part_begin += msg_width
            parts.append(spaces
                         + self.msg[:content_part_begin:])
            self.content = self.current_mark + " " + "\n".join(parts)


    def prepare_next_frame(self):
        if not self._done:
            self.current_mark = self.spinners[next(self.spinner_cursor)]
        else:
            self.current_mark = "v"
            self.msg = self._msg_done
        
        self.content = self.current_mark + " " + self.msg
        next(self.spinner_cursor)

    def done(self):
        self._done = True


class Message:
    def __init__(self, sender, name):
        self.sender = sender
        self.name = name


class Timer:
    def __init__(self, time, msg, target, *kb_args, **kb_kwargs):
        self._interval = time 
        self.msg = msg
        self.target = target
    
    async def run(self) -> None:
        await asyncio.sleep(self._interval)
        await self.target.post_message(Message(self, self.msg))


class Console:
    def __init__(self):
        pass


class View:
    def __init__(self,
                 height: Optional[int] = None,
                 width: Optional[int] = None):
        term_size = shutil.get_terminal_size((80, 24))
        self.height = height if height is not None else term_size.lines
        self.width = width if width is not None else term_size.columns

        self.widgets_lock = Lock()
        self._widgets = OrderedDict()
        self.widgets_to_be_deleted = list()

    def __setitem__(self, name, widget):
        with self.widgets_lock:
            if len(widget) > self.width:
                widget.wrap(self.width) 

            self._widgets[name] = widget

    def __getitem__(self, name):
        with self.widgets_lock:
            return self._widgets[name]

    def __delitem__(self, name):
        with self.widgets_lock:
            widget = self._widgets[name]
            del self._widgets[name]
            self.widgets_to_be_deleted.append(widget)

    @property
    def widgets(self):
        return self._widgets.values()

    def clear_widgets_to_be_deleted(self):
        self.widgets_to_be_deleted.clear()

    async def next_frame(self):
        for w in self.widgets:
            if w.is_animatable:
                w.prepare_next_frame()

    @property
    def need_animate(self):
        return any([w.is_animatable for w in self.widgets])


@lru_cache(maxsize=2048)
def count_parameters(func: Callable) -> int:
    """Count the number of parameters in a callable"""
    return len(signature(func).parameters)


async def invoke(callback: Callable, *params: object) -> Any:
    """Invoke a callback with an arbitrary number of parameters.
    Args:
        callback (Callable): [description]
    Returns:
        Any: [description]
    """
    parameter_count = count_parameters(callback)

    result = callback(*params[:parameter_count])
    if isawaitable(result):
        result = await result
    return result


class UI:
    def __init__(self):
        self.widgets_lock = threading.Lock()
        self.view = View()

        self._message_queue: Queue = Queue()
        self._child_tasks: WeakSet[Task] = WeakSet()

        self.height_previous_scene = 0

        self.running = True

    async def stop(self):
        self.running = False

    def refresh(self, repaint: bool = True, layout: bool = False) -> None:
        sys.stdout.write("\x1bP=1s\x1b\\")
        sys.stdout.write("\x1bP=2s\x1b\\")
        pass

    async def process_messages(self) -> None:
        while self.running:
            self.draw_scene()
            if self.view.need_animate:
                self._child_tasks.add(asyncio.create_task(Timer(1 / 15, "next_frame", self).run()))

            message = await self._message_queue.get()
            await self.dispatch_message(message)

            self.refresh()
            self.delete_scene()

    def draw_scene(self):
        self.height_previous_scene = 0

        with self.view.widgets_lock:
            for w in self.view.widgets_to_be_deleted:
                sys.stdout.write(f"{w.content}\n")
                self.height_previous_scene += w.height

            for w in self.view.widgets:
                sys.stdout.write(f"{w.content}\n")
                self.height_previous_scene += w.height

                if w.animated:
                    w.prepare_next_frame()

        self.view.clear_widgets_to_be_deleted()

    def delete_scene(self):
        with self.widgets_lock:
            sys.stdout.write(f"\033[1A\033[2K" * self.height_previous_scene) 

    async def dispatch_message(self, message):
        method_name = f"handle_{message.name}"

        method = getattr(self, method_name, None)
        if method is not None:
            await invoke(method, message)

    async def post_message(self, message: Message) -> bool:
        await self._message_queue.put(message)
        return True

    async def handle_next_frame(self):
        await self.view.next_frame()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return


