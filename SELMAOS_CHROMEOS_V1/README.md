# SelmaOS for Chromebooks

This package installs the SelmaOS local runtime into the ChromeOS Linux development environment. It binds only to `127.0.0.1:8765`, keeps state under the user's XDG data directory, and adds a launcher entry. Root access is not required.

## Install

Enable the Chromebook Linux development environment, clone or extract this repository, then run:

```bash
chmod +x SELMAOS_CHROMEOS_V1/*.sh SELMAOS_CHROMEOS_V1/selmaos-*
./SELMAOS_CHROMEOS_V1/install.sh
~/.local/bin/selmaos-open
```

To start the runtime automatically with the Linux environment:

```bash
./SELMAOS_CHROMEOS_V1/install.sh --enable-service
```

The local language model endpoint defaults to `http://127.0.0.1:8080/v1`. SelmaOS refuses remote endpoints when the interface requests offline-only mode.

## Remove

```bash
./SELMAOS_CHROMEOS_V1/uninstall.sh
```

Add `--purge-data` to remove conversation memory, safety state, audit data, and logs.
