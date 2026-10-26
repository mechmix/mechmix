#!/usr/bin/python3
"""Local Visio to PDF converter. No third-party Python packages required."""
import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile
import sys
import zipfile
from platform_tools import downloads_dir
from engine_support import run_engine, failure_message

TITLE = 'Visio, SOR, TRC & BDR to PDF'

def engine():
    from portable_runtime import engine_directory
    candidate = engine_directory() / 'program/soffice.com'
    if not candidate.is_file():
        raise RuntimeError('The bundled office engine is incomplete.')
    return str(candidate)

def convert(source, destination, executable=None):
    source = pathlib.Path(source).resolve()
    if source.suffix.lower() not in ('.vsdx', '.vsd', '.sor', '.trc', '.bdr'):
        raise ValueError('Please select a .vsdx, .vsd, .sor, EXFO .trc or .bdr file.')
    if not source.is_file():
        raise ValueError('The source file could not be found.')
    destination = pathlib.Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    temp_base=None
    if os.name=='nt':
        from portable_runtime import cache_root
        temp_base=cache_root()/'jobs';temp_base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='job-',dir=temp_base) as tmp:
        root = pathlib.Path(tmp)
        # Normalize the name to isolate input filenames from command-line options.
        extension = source.suffix.lower()
        if extension == '.vsdx':
            with source.open('rb') as stream:
                signature = stream.read(8)
            if signature == bytes.fromhex('D0CF11E0A1B11AE1'):
                extension = '.vsd'
            else:
                try:
                    with zipfile.ZipFile(source) as archive:
                        damaged=archive.testzip()
                        if damaged:raise ValueError('This VSDX contains a damaged ZIP entry. Download a fresh local copy before converting.')
                        if 'visio/document.xml' not in archive.namelist():
                            raise ValueError('No Visio drawing document exists inside this file.')
                except zipfile.BadZipFile as error:
                    raise ValueError('This VSDX file is not a readable Visio ZIP package.') from error
        input_path = root / ('drawing' + extension)
        shutil.copyfile(source, input_path)
        if extension=='.vsdx':
            from vsdx_compat import normalize_shape_ids
            normalize_shape_ids(input_path)
        output_dir = root / 'converted'
        output_dir.mkdir()
        pdf = output_dir / 'drawing.pdf'
        if source.suffix.lower() == '.sor':
            from sor_report import create_report
            create_report(source, pdf)
        elif source.suffix.lower() == '.bdr':
            from bdr_report import create_report
            create_report(source, pdf)
        elif source.suffix.lower() == '.trc':
            from trc_report import create_report
            create_report(source, pdf)
        else:
            executable = executable or engine()
            # File URLs avoid Windows path/encoding ambiguities. Retry automatic format
            # detection with a fresh profile if the explicit Visio import fails.
            for attempt in range(2):
                pdf.unlink(missing_ok=True)
                arguments=[executable, '-env:UserInstallation=' + (root / ('profile-'+str(attempt))).as_uri(), '--headless', '--nologo', '--nodefault', '--norestore']
                if attempt==0:arguments.append('--infilter=Visio Document')
                arguments+=['--convert-to','pdf:draw_pdf_Export','--outdir',str(output_dir),input_path.as_uri()]
                result=run_engine(arguments)
                if result.returncode==0 and pdf.exists() and pdf.read_bytes().startswith(b'%PDF-'):break
            else:raise RuntimeError(failure_message(result))
        # Exclusive creation prevents accidental replacement of existing PDFs.
        for number in range(10000):
            suffix = '' if number == 0 else ' (' + str(number + 1) + ')'
            target = destination / (source.stem + suffix + '.pdf')
            try:
                stream = target.open('xb')
            except FileExistsError:
                continue
            try:
                with stream, pdf.open('rb') as original:
                    shutil.copyfileobj(original, stream)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            return target
        raise RuntimeError('Too many PDFs have the same name in this folder.')

def main():
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument('files', nargs='*')
    parser.add_argument('--out', type=pathlib.Path)
    parser.add_argument('--web', action='store_true')
    args = parser.parse_args()
    try:
        if args.web or not args.files:
            from server import main as web_main
            web_main()
            return 0
        destination = args.out or downloads_dir()
        failures = []
        for file in args.files:
            try:
                result = convert(file, destination)
                print('Saved: ' + str(result))
            except Exception as error:
                failures.append(file)
                print(str(error), file=sys.stderr)
        return 1 if failures else 0
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        print('Could not start the converter: ' + str(error), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
