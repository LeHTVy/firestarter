"""Process Streamer - PTY-based process execution for real-time streaming.

Handles execution of subprocesses using pseudo-terminals (pty) to ensure
output is streamed immediately (unbuffered) rather than block-buffered.
"""

import os
import sys
import time
import select
import subprocess
import threading
import queue
from typing import List, Dict, Any, Optional, Tuple, Generator

class ProcessStreamer:
    """Executes processes attached to a PTY for real-time output."""
    
    def __init__(self):
        self.output_queue = queue.Queue()
        
    def execute(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> Generator[str, None, int]:
        """Execute a command in a PTY and yield output lines.
        
        Args:
            command: Command and arguments list
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds
            
        Yields:
            Output lines from stdout/stderr combined
            
        Returns:
            Exit code (when generator is exhausted, but generators can't actually return values in a simple loop)
            The generator will just raise StopIteration. 
            To get the exit code, we might need a different pattern or just attach it to the instance.
        """
        
        if sys.platform == "win32":
            return self._execute_subprocess_fallback(command, cwd, env, timeout)
            
        return self._execute_pty(command, cwd, env, timeout)

    def _execute_pty(
        self,
        command: List[str],
        cwd: Optional[str],
        env: Optional[Dict[str, str]],
        timeout: Optional[int]
    ) -> Generator[str, None, int]:
        """Execute using python's pty module (Linux/macOS)."""
        import pty
        import errno
        
        master_fd, slave_fd = pty.openpty()
        
        try:
            process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=cwd,
                env=env,
                close_fds=True,
                preexec_fn=os.setsid
            )
        except Exception as e:
            os.close(master_fd)
            os.close(slave_fd)
            raise e

        # Close slave fd in parent process
        os.close(slave_fd)
        
        start_time = time.time()
        buffer = []
        
        try:
            while True:
                # Check timeout
                if timeout and (time.time() - start_time > timeout):
                    process.terminate()
                    yield f"\n[TIMEOUT after {timeout}s]\n"
                    break
                
                try:
                    # Select with timeout
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    
                    if master_fd in r:
                        try:
                            data = os.read(master_fd, 4096)
                            if not data:  # EOF
                                break
                                
                            decoded = data.decode('utf-8', errors='replace')
                            for char in decoded:
                                if char == '\r':
                                    line = "".join(buffer)
                                    buffer = []
                                    yield line
                                elif char == '\n':
                                    line = "".join(buffer)
                                    buffer = []
                                    yield line
                                else:
                                    buffer.append(char)
                        except OSError as e:
                            # EIO (Errno 5) means EOF on Linux PTY
                            if e.errno == errno.EIO:
                                break
                            raise e
                    
                    # Only break if process is done AND no more data to read (checked via select)
                    elif process.poll() is not None:
                        break
                        
                except (OSError, select.error):
                    break
                    
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
            
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=1.0)
                except:
                    pass
        
        # Flush remaining buffer
        if buffer:
            yield "".join(buffer)
            
        return process.returncode if process.returncode is not None else -1

    def _execute_subprocess_fallback(self, command, cwd, env, timeout):
        """Fallback for non-PTY systems."""
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
            text=True,
            bufsize=1
        )
        
        start_time = time.time()
        
        while True:
            if timeout and (time.time() - start_time > timeout):
                process.terminate()
                yield f"\n[TIMEOUT]\n"
                break
                
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            
            if line:
                yield line.rstrip()
                
        return process.returncode

    def _execute_winpty(self, command, cwd, env, timeout):
        """Windows PTY execution (placeholder)."""
        pass
