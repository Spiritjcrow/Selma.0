"""Private local storage permissions for SelmaOS-owned paths (POSIX/Termux)."""
import os
import stat


def private_directory(path):
    path = os.path.abspath(os.path.expanduser(os.fspath(path)))
    if os.path.islink(path):
        raise PermissionError("private storage directory cannot be a symlink")
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.path.islink(path) or not os.path.isdir(path):
        raise PermissionError("private storage directory is not a real directory")
    os.chmod(path, 0o700)
    return path


def private_file(path):
    path = os.path.abspath(os.path.expanduser(os.fspath(path)))
    if os.path.islink(path):
        raise PermissionError("private storage file cannot be a symlink")
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PermissionError("private storage path is not a regular file")
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    return path
