import argparse
import csv
from itertools import chain
import os
import re
from collections import defaultdict
from datetime import datetime

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

QUARTER_LABELS = {1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4'}
TRACK_COLUMNS = ['DATE', 'TIME', 'ARTIST', 'SONG', 'DURATION']

TRACK_FILENAME_RE = re.compile(r'^STrack-(\d{6,8})\.csv$', re.IGNORECASE)


def parse_filename_date(filename: str):
    match = TRACK_FILENAME_RE.match(filename)
    if not match:
        return None
    date_token = match.group(1)
    for fmt in ('%y%m%d', '%Y%m%d'):
        try:
            return datetime.strptime(date_token, fmt).date()
        except ValueError:
            continue
    return None


def get_quarter_label(date_obj):
    quarter = (date_obj.month - 1) // 3 + 1
    return f'{date_obj.year}-{QUARTER_LABELS[quarter]}'


def read_track_file(filepath):
    rows = []
    with open(filepath, newline='', encoding='utf-8-sig', errors='replace') as f:
        sample = f.read(8192)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t')
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = '\t' if '\t' in sample else ','

        reader = csv.reader(f, delimiter=delimiter)
        first_row = next(reader, None)
        if first_row is None:
            return rows

        header_indexes = {name.strip().upper(): index for index, name in enumerate(first_row)}
        has_header = all(column in header_indexes for column in TRACK_COLUMNS)
        if has_header:
            data_rows = reader
            column_indexes = [header_indexes[column] for column in TRACK_COLUMNS]
        else:
            data_rows = chain((first_row,), reader)
            column_indexes = list(range(len(TRACK_COLUMNS)))

        for row in data_rows:
            if len(row) < len(TRACK_COLUMNS):
                continue
            normalized = {
                column: row[index].strip()
                for column, index in zip(TRACK_COLUMNS, column_indexes)
            }
            if all(normalized.values()):
                rows.append(normalized)
    return rows


def write_quarter_csv(output_dir, quarter_label, rows):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f'tracks_{quarter_label}.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=TRACK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_all_csv(output_dir, rows):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, 'all_quarters_tracks.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=TRACK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_xlsx(output_dir, rows, progress_callback=None):
    if Workbook is None:
        raise RuntimeError('openpyxl is required to export XLSX. Install from requirements.txt')
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, 'quarterly_tracks.xlsx')
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Tracks'
    sheet.append(TRACK_COLUMNS)
    if progress_callback is not None:
        progress_callback('building', 0, len(rows))
    report_interval = max(1, len(rows) // 100)
    for index, row in enumerate(rows, start=1):
        sheet.append([row[col] for col in TRACK_COLUMNS])
        if progress_callback is not None and (index % report_interval == 0 or index == len(rows)):
            progress_callback('building', index, len(rows))
    if progress_callback is not None:
        progress_callback('saving', len(rows), len(rows))
    workbook.save(path)
    if progress_callback is not None:
        progress_callback('saved', len(rows), len(rows))
    return path


def discover_input_files(input_dir):
    if not os.path.isdir(input_dir):
        raise FileNotFoundError(f'Input directory not found: {input_dir}')
    files = []
    for name in os.listdir(input_dir):
        if TRACK_FILENAME_RE.match(name):
            fullpath = os.path.join(input_dir, name)
            if os.path.isfile(fullpath):
                files.append(fullpath)
    return sorted(files)


def aggregate_by_quarter(filepaths, progress_callback=None):
    quarter_rows = defaultdict(list)
    all_rows = []
    for index, path in enumerate(filepaths, start=1):
        date_obj = parse_filename_date(os.path.basename(path))
        quarter_label = get_quarter_label(date_obj) if date_obj else 'unknown'
        rows = read_track_file(path)
        quarter_rows[quarter_label].extend(rows)
        all_rows.extend(rows)
        if progress_callback is not None:
            progress_callback(index, len(filepaths))
    return quarter_rows, all_rows


def parse_args():
    parser = argparse.ArgumentParser(description='Aggregate STrack CSVs into quarterly track datasets.')
    parser.add_argument('--input', '-i', required=False, help='Source directory containing STrack-*.csv files')
    parser.add_argument('--output', '-o', required=False, help='Output directory for quarterly CSV and XLSX files')
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.input and not args.output:
        from quarterly_track_loader_webview import launch
        launch()
        return

    input_dir = args.input
    output_dir = args.output

    if not input_dir:
        try:
            input_dir = input('Enter input directory containing STrack-*.csv files: ').strip()
        except EOFError:
            raise SystemExit('Input directory not provided.')

    if not output_dir:
        default_output = os.path.join(os.path.expanduser('~'), 'Desktop', 'quarterly_track_loader_output')
        try:
            resp = input(f'Enter output directory for generated files [default: {default_output}]: ').strip()
        except EOFError:
            resp = ''
        output_dir = resp or default_output

    filepaths = discover_input_files(input_dir)
    if not filepaths:
        raise SystemExit('No STrack-*.csv files found in the input directory.')
    quarter_rows, all_rows = aggregate_by_quarter(filepaths)
    output_paths = []
    for quarter, rows in sorted(quarter_rows.items()):
        output_paths.append(write_quarter_csv(output_dir, quarter, rows))
    output_paths.append(write_all_csv(output_dir, all_rows))
    output_paths.append(write_xlsx(output_dir, all_rows))
    print('Generated output files:')
    for path in output_paths:
        print(' -', path)


if __name__ == '__main__':
    main()
