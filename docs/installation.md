# Installing AstroTwo

AstroTwo 1.0 is for macOS. **Windows and Linux packages are in preparation for version 1.1**: the instructions for them are below ([Windows](#windows), [Linux](#linux)), with their [limits](#limits-on-windows-and-linux).

## Requirements

- **macOS 15 (Sequoia) or later**
- **Apple silicon** (M1 or later). Intel Macs are not supported.
- An internet connection for online surveys, catalogues and services. Files on your Mac (FITS images, catalogues, MOCs, saved sessions) open without a connection.
- Optional, for the AI assistant: an API key from a supported provider, or a local model in Ollama or LM Studio. See [the AI assistant](quickstart.md#9-the-ai-assistant-optional).

## Install the app

1. From the [Releases](https://github.com/guidogg13/AstroTwo/releases) page, download both files of the latest version into the same folder, for example *Downloads*:
   - `AstroTwo-<version>.dmg`, the disk image;
   - `AstroTwo-<version>.dmg.sha256`, its SHA-256 checksum.
2. Check the download (see [Verify the download](#verify-the-download) below).
3. Double-click the `.dmg`. A window named **AstroTwo <version>** opens with two items: **AstroTwo** and a shortcut to **Applications**.
4. Drag **AstroTwo** onto the **Applications** shortcut in the same window. This copies the app into your *Applications* folder. Python and all the libraries AstroTwo needs are inside the app. You do not need to install anything else.
5. Eject the disk image: click the eject button next to **AstroTwo <version>** in the Finder sidebar. You can then delete the `.dmg`.
6. Start AstroTwo from *Applications*. Do not run it from inside the disk image.

### Verify the download

The `.sha256` file holds the SHA-256 checksum of the `.dmg` as published with the release. If the two match, the file you downloaded is exactly the published one: not damaged and not changed.

1. Open **Terminal** (in *Applications → Utilities*).
2. Go to the folder with the two files, for example:

   ```bash
   cd ~/Downloads
   ```

3. Run, with the version you downloaded:

   ```bash
   shasum -a 256 -c AstroTwo-<version>.dmg.sha256
   ```

4. The answer must be one line ending in **OK**:

   ```text
   AstroTwo-<version>.dmg: OK
   ```

   If it says **FAILED**, or that the file is missing, do not open the `.dmg`. Delete it and download it again. If it fails again, please open an issue on GitHub.

`-c` makes `shasum` read the checksum and the file name from the `.sha256` file and compare. You can also print the checksum with `shasum -a 256 AstroTwo-<version>.dmg` and compare it by eye with the one on the release page.

### First launch: AstroTwo is not signed by Apple

**Version 1.0 is not signed with an Apple Developer ID and is not notarized by Apple.** The app has only an *ad hoc* signature: macOS can check that the app was not changed after it was built, but Apple has not checked the developer or scanned the app. This is a choice of the project for the first version: signing and notarization need a paid Apple Developer account, and they will come in a later version. Until then, macOS blocks the first launch of the downloaded app, and you allow it once by hand.

**Before you allow it, check the download** with its SHA-256 checksum ([Verify the download](#verify-the-download)). The checksum is how you know that the app is exactly the one published on the Releases page. Do not open an AstroTwo `.dmg` whose checksum does not match.

On **macOS 15 (Sequoia) and later**:

1. Copy AstroTwo into *Applications* (steps above) and double-click it once. macOS shows a warning that it could not verify AstroTwo and does not open it. Close the warning (**Done**). Do **not** choose to move the app to the Bin.
2. Open the **Apple menu → System Settings**, then click **Privacy & Security** in the sidebar.
3. Scroll down to the **Security** section. There is a message saying that AstroTwo was blocked. Click **Open Anyway** next to it. The button is there for about one hour after you tried to open the app; if it is not there, repeat step 1.
4. macOS asks again: click **Open Anyway**, then enter your login password and click **OK**.

AstroTwo starts. From then on it opens normally with a double-click. You need to do this once for each new version.

On macOS 15 and later, Control-clicking the app and choosing **Open** no longer skips this check: use **Open Anyway** in System Settings as above.

## Windows

*Version 1.1 and later. Not yet published: the packages are being tested.*

Requirements: **Windows 10 or 11, 64-bit (x86_64)**. On Windows 11 on ARM the x86_64 package runs through Windows' built-in emulation. Graphics with **OpenGL 4.1** for the sky view; without it, see [Limits](#limits-on-windows-and-linux).

1. From the [Releases](https://github.com/guidogg13/AstroTwo/releases) page, download `AstroTwo-<version>-windows-x86_64.zip` and `AstroTwo-<version>-windows-x86_64.zip.sha256` into the same folder.
2. Check the download in **PowerShell**, in that folder:

   ```powershell
   (Get-FileHash .\AstroTwo-<version>-windows-x86_64.zip -Algorithm SHA256).Hash.ToLower()
   Get-Content .\AstroTwo-<version>-windows-x86_64.zip.sha256
   ```

   The two 64-character values must be equal. If they differ, delete the zip and download it again.
3. Right-click the zip → **Extract All…**, and choose a folder you own, for example `C:\Users\<you>\AstroTwo-<version>`. No administrator rights are needed and nothing is installed in the system.
4. Open the extracted **AstroTwo** folder and double-click **AstroTwo.exe**.

**SmartScreen.** The Windows package is not signed with a code-signing certificate. The first time, Windows may show *"Windows protected your PC"*. After checking the SHA-256 (step 2), click **More info**, then **Run anyway**. Windows remembers the choice for that copy of the program.

To uninstall, delete the extracted folder. To remove the data too, delete `%LOCALAPPDATA%\AstroTwo\`; API keys can be deleted from the assistant settings or in *Credential Manager → Windows Credentials* (entries `dev.pages.astrotwo.ai`).

## Linux

*Version 1.1 and later. Not yet published: the packages are being tested.*

Requirements: **64-bit x86_64 Linux with glibc 2.35 or later** (for example Ubuntu 22.04, Debian 12, Fedora 36, RHEL 9 and later), an X11 or Wayland desktop. Two packages with the same content:

- `AstroTwo-<version>-linux-x86_64.AppImage`: one file, nothing to install. It does not need FUSE 2 (static runtime).
- `AstroTwo-<version>-linux-x86_64.tar.gz`: the same program as a folder.

Download the package and its `.sha256` file into the same folder, then:

```bash
sha256sum -c AstroTwo-<version>-linux-x86_64.AppImage.sha256   # must print: OK
chmod +x AstroTwo-<version>-linux-x86_64.AppImage
./AstroTwo-<version>-linux-x86_64.AppImage
```

or, with the `.tar.gz`:

```bash
sha256sum -c AstroTwo-<version>-linux-x86_64.tar.gz.sha256
tar xzf AstroTwo-<version>-linux-x86_64.tar.gz
./AstroTwo/AstroTwo
```

**API keys on Linux** are kept in the desktop's **Secret Service** (GNOME Keyring, KWallet 5.97 or later, KeePassXC with Secret Service enabled). If no Secret Service is running (for example on a server without a desktop session), the assistant says that the key store is not available; everything else works.

To uninstall, delete the AppImage or the folder. To remove the data too, delete `~/.cache/astrotwo/` and `~/.local/share/astrotwo/` (or the folders under `$XDG_CACHE_HOME` and `$XDG_DATA_HOME`, if you set them).

## Limits on Windows and Linux

- **Only x86_64.** There is no native package for Windows on ARM or Linux on ARM: some scientific libraries AstroTwo uses are not available for those systems yet.
- **Software OpenGL fallback.** The sky view needs OpenGL 4.1. In virtual machines, remote desktops or with old drivers it may not be there: AstroTwo then says so and, from the next start, draws the sky in software (Mesa *llvmpipe*), which is slower. The status bar and the messages say when the software fallback is in use. To choose yourself, start AstroTwo with the environment variable `ASTROTWO_OPENGL=software` or `ASTROTWO_OPENGL=native`. On macOS there is no fallback.
- **Sessions are not portable between systems.** A session file stores the full paths of the files you opened (`C:\…` on Windows, `/home/…` on Linux, `/Users/…` on macOS), so a session saved on one system does not reopen on another. Exported data files (CSV, ECSV, VOTable, FITS, MOC) are byte-for-byte the same on every system; PNG and PDF exports have the same content but may differ in fonts and dates.
- **Keyboard shortcuts** without the Windows/Super key: full screen **F11**, night mode **Ctrl+Shift+N**, assistant **Ctrl+Shift+A**, settings **Ctrl+,**. On macOS: ⌃⌘F, ⌃⌘N, ⌃⌘A, ⌘,.
- **Not signed.** Neither package is signed (Windows SmartScreen asks once; see above). Check the SHA-256 of every download.

## Run from source (for developers)

Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 and the dependencies listed in `pyproject.toml`.

```bash
git clone https://github.com/guidogg13/AstroTwo.git
cd AstroTwo
uv run astrotwo
```

The tests run with:

```bash
uv run python -m pytest -q
```

The default test suite never uses the network. Tests that need real online services are marked `network` and run separately.

## Where AstroTwo keeps its files

- **Cache** of tiles, catalogues and service answers: `~/Library/Caches/AstroTwo/`. Its size limit is set in *Settings*.
- **Saved object profiles and tables received through SAMP:** `~/Library/Application Support/AstroTwo/`.
- **API keys for the AI assistant:** only in the **macOS Keychain**, never in files or logs.

On Windows and Linux (version 1.1):

| | Windows | Linux |
|---|---|---|
| Cache | `%LOCALAPPDATA%\AstroTwo\Cache\` | `~/.cache/astrotwo/` (`$XDG_CACHE_HOME/astrotwo/`) |
| Object profiles, SAMP tables | `%LOCALAPPDATA%\AstroTwo\` | `~/.local/share/astrotwo/` (`$XDG_DATA_HOME/astrotwo/`) |
| API keys | Windows Credential Manager | Secret Service (GNOME Keyring, KWallet, KeePassXC) |
| Settings | registry, `HKEY_CURRENT_USER\Software\pages.dev\astrotwo` | `~/.config/pages.dev/astrotwo.conf` |

## Uninstall

Drag AstroTwo from *Applications* to the Bin. To remove its data as well, delete `~/Library/Caches/AstroTwo/` and `~/Library/Application Support/AstroTwo/`. API keys can be deleted from the assistant settings (**Delete** next to the key), or with the *Keychain Access* app.
