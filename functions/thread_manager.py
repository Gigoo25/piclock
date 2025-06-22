import logging
import threading


class ThreadManager:
    """
    Manages all threads in the application.

    This class provides centralized thread management with:
    - Shared lock and events for synchronization
    - Error handling for all threads
    - Clean shutdown mechanism
    """

    def __init__(self):
        self.threads = []
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.tick_event = threading.Event()

    def add_thread(self, target, args=(), kwargs=None):
        """
        Add a thread with the specified target and arguments.

        Args:
            target: The function to run in the thread
            args: Positional arguments to pass to the target function
            kwargs: Keyword arguments to pass to the target function

        Returns:
            The created thread object
        """
        if kwargs is None:
            kwargs = {}

        thread = threading.Thread(
            target=self._thread_wrapper, args=(target, args, kwargs)
        )
        self.threads.append(thread)
        return thread

    def _thread_wrapper(self, target, args, kwargs):
        """
        Wrapper that adds error handling to threads.

        Args:
            target: The function to run
            args: Positional arguments for the target
            kwargs: Keyword arguments for the target
        """
        try:
            # Pass the stop_event to all thread functions
            target(*args, **kwargs, stop_event=self.stop_event)
        except Exception as e:
            logging.error(f"Exception in thread {target.__name__}: {e}")

    def start_all(self):
        """Start all registered threads."""
        for thread in self.threads:
            thread.start()
            logging.info(f"Started thread: {thread.name}")

    def stop_all(self):
        """Signal all threads to stop and wait for them to finish."""
        self.stop_event.set()
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2.0)  # Wait up to 2 seconds for each thread
        logging.info("All threads stopped")

    def is_stopping(self):
        """Check if stop has been requested."""
        return self.stop_event.is_set()
