# Local FFmpeg tools

Installed for development: Gyan Windows x64 FFmpeg 9.0.1 essentials build.
The binary directory is ignored; it is not bundled as application source.

- [FFmpeg's list of Windows build providers](https://ffmpeg.org/download.html)
- [Gyan release](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.1)
- Archive: `ffmpeg-9.0.1-essentials_build.zip`
- Verified SHA-256: `fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9`
- [Published checksum](https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.zip.sha256)

For another checkout, download the archive from that release, verify the checksum and copy `bin/ffprobe.exe` and `bin/ffmpeg.exe` into this folder's `bin/` directory. Retain the supplied LICENSE. Alternatively install FFmpeg yourself and set FFPROBE_PATH or PATH. The app automatically discovers the project-local ffprobe only when using the default `ffprobe` setting. No system PATH changes are made.
