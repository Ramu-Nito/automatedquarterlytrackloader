# Automated Quarterly Track Loader

This repository combines prepared `STrack-*.csv` files by calendar quarter and exports the tracks as CSV and XLSX. These files already contain only the tracks marked for export, so raw `SLog` logs are not processed.

## What it does
- Reads prepared track files from a source directory
- Detects quarter from filenames like `STrack-261004.csv`
- Reads headerless tab-delimited or comma-delimited files, using the first five fields as `DATE`, `TIME`, `ARTIST`, `SONG`, and `DURATION`
- Ignores any additional metadata fields after `DURATION`
- Writes one CSV per quarter and a consolidated `quarterly_tracks.xlsx`

## Desktop app

Double-click `run_quarterly_track_loader.bat` to open the app. Leave the log folder blank to use the usual log location; the default is intentionally not shown. Choose an output folder or keep the suggested Desktop folder, then select **Build quarterly files**. The progress bar tracks reading and exporting, and **Open output folder** takes you to the results.

To make a standalone Windows app, run `build_windows_app.bat` once on a build computer with Python and internet access. This creates `dist/QuarterlyTrackLoader-Web.exe`, which bundles Python, the HTML interface, and spreadsheet support; the receiving computer does not need Python or an internet connection. The launcher prefers this current executable when present.

Without the standalone executable, the launcher uses installed Python 3.9+ and checks and installs dependencies automatically if needed; that first-time install requires internet access. The interface uses Microsoft Edge WebView2 Runtime, which is included with many Windows installations. The standalone app still requires that Windows runtime.

## Command-line usage

Python 3.8+ and `openpyxl` are required for command-line use. The desktop app additionally uses `pywebview`. Install app dependencies manually if needed:

```powershell
python -m pip install -r requirements.txt
```

## Usage

```powershell
python quarterly_track_loader.py --input "C:\path\to\track-files" --output "C:\path\to\output"
```

This creates:
- `output/tracks_2025-Q1.csv` (and other quarter CSVs)
- `output/all_quarters_tracks.csv`
- `output/quarterly_tracks.xlsx`

## Windows launcher

A batch file launches the app without a console window. To use the legacy command-line mode, pass input and output folders:

```powershell
run_quarterly_track_loader.bat "C:\path\to\input" "C:\path\to\output"
```

Without arguments, the batch file opens the desktop app. With two folder arguments, it runs the command-line workflow.

## Notes
- The loader only processes files named `STrack-YYMMDD.csv` or `STrack-YYYYMMDD.csv`.
- Only the five requested columns are preserved in the final dataset.
