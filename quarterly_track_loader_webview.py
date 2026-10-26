import importlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import quarterly_track_loader as loader


DEFAULT_INPUT_DIR = r'\\UE3JRGH-LBPLAYOUT\Logs'
DEFAULT_OUTPUT_DIR = os.path.join(os.path.expanduser('~'), 'Desktop', 'quarterly_track_loader_output')


class LoaderApi:
    def __init__(self):
        self.window = None
        self.output_dir = ''
        self._busy = False
        self._lock = threading.Lock()

    def get_defaults(self):
        return {'output_dir': DEFAULT_OUTPUT_DIR}

    def browse_input(self, current=''):
        return self._browse_folder(current)

    def browse_output(self, current=''):
        return self._browse_folder(current)

    def _browse_folder(self, current):
        import webview

        initial = current.strip() if current else ''
        selected = self.window.create_file_dialog(
            webview.FileDialog.FOLDER,
            directory=initial if initial and os.path.isdir(initial) else None,
        )
        return selected[0] if selected else ''

    def start_job(self, source_dir, output_dir):
        with self._lock:
            if self._busy:
                return {'started': False, 'message': 'A job is already running.'}
            if not output_dir.strip():
                return {'started': False, 'message': 'Choose a folder for the finished files.'}
            self._busy = True

        resolved_source = source_dir.strip() or DEFAULT_INPUT_DIR
        threading.Thread(target=self._run_job, args=(resolved_source, output_dir.strip()),
                         daemon=True).start()
        return {'started': True}

    def _run_job(self, source_dir, output_dir):
        job_started = time.monotonic()
        save_progress_stop = threading.Event()
        save_monitor = None
        try:
            self._emit(status='Checking the track folder...', percent=0,
                       indeterminate=True, phase='busy')
            if not os.path.isdir(source_dir):
                raise RuntimeError('The track folder is unavailable. Check the usual location or choose another folder.')

            self._emit(status='Checking required components...', percent=0,
                       indeterminate=True, phase='busy')
            self._ensure_spreadsheet_dependency()
            self._emit(status='Finding STrack files...', percent=0,
                       indeterminate=True, phase='busy')
            files = loader.discover_input_files(source_dir)
            if not files:
                raise RuntimeError('No matching STrack CSV files were found in that folder.')

            def report_file_progress(current, total):
                percent = int(current / total * 68)
                elapsed = max(0.1, time.monotonic() - job_started)
                remaining = elapsed / current * (total - current) + max(1, total * 0.2)
                self._emit(status=f'Reading track files {current} of {total}',
                           percent=percent, indeterminate=False, phase='busy',
                           eta=self._format_eta(remaining))

            quarter_rows, all_rows = loader.aggregate_by_quarter(files, report_file_progress)
            csv_steps = len(quarter_rows) + 1
            completed = 0
            output_paths = []
            self._emit(status='Writing quarterly files...', percent=70,
                       indeterminate=False, phase='busy', eta='Estimating remaining time...')
            csv_started = time.monotonic()

            for quarter, rows in sorted(quarter_rows.items()):
                output_paths.append(loader.write_quarter_csv(output_dir, quarter, rows))
                completed += 1
                self._report_output_progress(completed, csv_steps, csv_started, len(all_rows))

            output_paths.append(loader.write_all_csv(output_dir, all_rows))
            completed += 1
            self._report_output_progress(completed, csv_steps, csv_started, len(all_rows))
            xlsx_started = time.monotonic()

            def report_xlsx_progress(stage, current, total):
                nonlocal save_monitor
                if stage == 'building':
                    elapsed = max(0.1, time.monotonic() - xlsx_started)
                    rate = current / elapsed if current else 0
                    append_remaining = (total - current) / rate if rate else total / 1000
                    estimated_save = max(1.5, total / 12000)
                    percent = 80 + (15 * current / max(total, 1))
                    self._emit(
                        status=f'Building spreadsheet - {current:,} of {total:,} rows',
                        percent=percent,
                        indeterminate=False,
                        phase='busy',
                        eta=self._format_eta(append_remaining + estimated_save),
                    )
                elif stage == 'saving':
                    append_elapsed = time.monotonic() - xlsx_started
                    estimated_save = max(1.5, append_elapsed * 0.75, total / 12000)
                    save_monitor = threading.Thread(
                        target=self._report_save_progress,
                        args=(save_progress_stop, estimated_save),
                        daemon=True,
                    )
                    save_monitor.start()
                elif stage == 'saved':
                    save_progress_stop.set()
                    self._emit(status='Finalizing workbook...', percent=99.5,
                               indeterminate=False, phase='busy', eta='')

            output_paths.append(loader.write_xlsx(
                output_dir, all_rows, progress_callback=report_xlsx_progress
            ))
            self.output_dir = output_dir
            self._emit(status='Finished. Your files are ready.', percent=100,
                       indeterminate=False, phase='success', show_output=True, eta='',
                       button_label='Run again')
        except Exception as error:
            self._emit(status=self._format_error(error), percent=0,
                       indeterminate=False, phase='error', show_output=False, eta='',
                       button_label='Try again')
        finally:
            save_progress_stop.set()
            if save_monitor is not None:
                save_monitor.join(timeout=1)
            with self._lock:
                self._busy = False

    def _report_output_progress(self, completed, total, started, row_count):
        elapsed = max(0.1, time.monotonic() - started)
        remaining_steps = total - completed
        step_rate = elapsed / completed
        estimate = remaining_steps * step_rate + row_count / 12000
        percent = 68 + int(completed / total * 12)
        self._emit(status=f'Writing CSV files {completed} of {total}', percent=percent,
                   indeterminate=False, phase='busy', eta=self._format_eta(estimate))

    def _report_save_progress(self, stop_event, estimated_seconds):
        started = time.monotonic()
        while not stop_event.wait(0.5):
            elapsed = time.monotonic() - started
            if elapsed < estimated_seconds:
                remaining_text = f' - about {self._format_duration(estimated_seconds - elapsed)} left'
                percent = 95 + min(4.5, 4.5 * elapsed / estimated_seconds)
            else:
                remaining_text = ' - taking longer than estimated'
                percent = 99.5
            self._emit(
                status=f'Saving spreadsheet - {self._format_duration(elapsed)} elapsed{remaining_text}',
                percent=percent,
                indeterminate=True,
                phase='busy',
                eta='',
            )

    @staticmethod
    def _format_duration(seconds):
        seconds = max(0, int(seconds + 0.5))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f'{hours}h {minutes}m'
        if minutes:
            return f'{minutes}m {seconds}s'
        return f'{seconds}s'

    @classmethod
    def _format_eta(cls, seconds):
        return f'~{cls._format_duration(seconds)} remaining'

    @staticmethod
    def _format_error(error):
        if isinstance(error, OSError):
            error_number = getattr(error, 'winerror', None) or error.errno
            message = error.strerror or str(error)
            if error_number is not None:
                return f'Error No. {error_number}: {message}'
            return f'Error: {message}'
        return f'Error: {error}'

    @staticmethod
    def _ensure_spreadsheet_dependency():
        if loader.Workbook is not None:
            return
        requirements = Path(__file__).with_name('requirements.txt')
        if not requirements.is_file():
            raise RuntimeError('The dependency list is missing; Excel export cannot be prepared.')

        commands = (
            [sys.executable, '-m', 'pip', 'install', '-r', str(requirements)],
            [sys.executable, '-m', 'pip', 'install', '--user', '-r', str(requirements)],
        )
        for command in commands:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, check=False)
            if result.returncode == 0:
                try:
                    loader.Workbook = importlib.import_module('openpyxl').Workbook
                    return
                except ImportError:
                    continue
        raise RuntimeError('Excel support could not be installed automatically. Check internet access and try again.')

    def open_output_folder(self):
        if not self.output_dir or not os.path.isdir(self.output_dir):
            return {'opened': False}
        try:
            if hasattr(os, 'startfile'):
                os.startfile(self.output_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.output_dir])
            else:
                subprocess.Popen(['xdg-open', self.output_dir])
            return {'opened': True}
        except OSError as error:
            self._emit(status=self._format_error(error), phase='error',
                       button_label='Try again')
            return {'opened': False}

    def _emit(self, **state):
        if self.window is None:
            return
        script = f'window.setJobState({json.dumps(state, ensure_ascii=True)})'
        try:
            self.window.evaluate_js(script)
        except Exception:
            pass


def _show_startup_error(message):
    import ctypes

    ctypes.windll.user32.MessageBoxW(None, message, 'Quarterly Track Loader', 0x10)


def launch():
    try:
        import webview
    except ImportError:
        _show_startup_error(
            'The WebView component is not installed. Run the Windows launcher to prepare the app.'
        )
        return

    page = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'quarterly_track_loader.html'
    if not page.is_file():
        _show_startup_error('The app interface is missing. Rebuild the Windows app.')
        return

    api = LoaderApi()
    api.window = webview.create_window(
        'Quarterly Track Loader',
        url=page.as_uri(),
        js_api=api,
        width=900,
        height=760,
        min_size=(760, 700),
        background_color='#163C3D',
    )
    try:
        webview.start(gui='edgechromium', debug=False)
    except Exception as error:
        error_number = getattr(error, 'winerror', None) or getattr(error, 'errno', None)
        number_text = f'Error No. {error_number}: ' if error_number is not None else 'Error: '
        _show_startup_error(
            'The Microsoft Edge WebView2 Runtime is required to display the app.\n\n'
            f'{number_text}{error}'
        )