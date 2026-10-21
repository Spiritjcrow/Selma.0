# Selma Universal Files v0.1

An **offline, stdlib-only** local-folder file browser designed as the first adapter behind a future universal SelmaOS storage interface. It is not an Android APK or a production hardened security boundary.

## Quick start (Python 3.11+)

From repository root:

```bash
python3 tools/selma_files_server.py --root "$HOME/Downloads" --port 8766
```

Open `http://127.0.0.1:8766` in the **same device**. Change the root to an accessible, user-owned directory, especially on Android/Termux (`~/storage/downloads` after granting Termux storage access). Stop with Ctrl+C. The app binds only to loopback; it does **not** accept connections from other devices.

## Tested contract / scope

- Two independent folder panes; responsive small-screen layout, filename filter, navigation.
- File copy, same-filesystem file move, and directory creation with confirmation for transfers.
- No delete operations, no overwriting. Source symlinks and traversal outside selected root denied.
- No cloud login, SMB/NFS, MTP, SAF, thumbnails, AI processing, model downloads, or network shares.
- `core.universal_files.FileProvider` is the future adapter contract; `LocalFileProvider` is the only implementation so far.
- No additional Python dependencies. File operations occur on the user's host only when run locally.

## Security/technical limitations

This is a prototype for a **trusted, user-owned root**. It does not defend against another local process swapping directories or symlinks concurrently (TOCTOU); do not expose it on a network or use it to serve untrusted multi-user folders. It has an in-memory CSRF token, same-origin write checks, loopback/Host restrictions, a small JSON request cap, and no directory traversal. File move uses `os.link` then unlink and is intentionally limited to the same filesystem. Copy may leave a partial output if the process itself crashes; neither operation has durable rollback. A separate, OS-native hardened storage adapter and recovery journal are needed before wider use.

## Verify

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

## Next milestones

1. Safe no-follow dirfd/handle-based Linux and Windows storage adapters with crash-safe staging/journaling.
2. Native Android Storage Access Framework (SAF) adapter and scoped storage permissions.
3. Opt-in indexed search, SMB/cloud adapters, encrypted credentials, async progress/cancel, and accessibility review.
