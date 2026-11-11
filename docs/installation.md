# Installing AstroTwo

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

### First launch

The app is not yet signed with an Apple Developer ID or notarized, so macOS blocks the first launch. To allow it:

1. Try to open AstroTwo once and close the warning.
2. Open **System Settings → Privacy & Security**.
3. Next to the message about AstroTwo, click **Open Anyway** and confirm.

You only need to do this once for each version.

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

## Uninstall

Drag AstroTwo from *Applications* to the Bin. To remove its data as well, delete `~/Library/Caches/AstroTwo/` and `~/Library/Application Support/AstroTwo/`. API keys can be deleted from the assistant settings (**Delete** next to the key), or with the *Keychain Access* app.
