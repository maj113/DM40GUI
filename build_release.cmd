@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "DEFAULT_MODE_FLAGS=--deployment"
set "DEFAULT_CONSOLE_MODE=disable"
set "DEFAULT_MSVC=latest"
set "DEFAULT_PYTHON=py -3.13"
set "DEFAULT_OUT_DIR=build\ci\nuitka"
set "DEFAULT_CCFLAGS=/GS- /Gw /Os /kernel /d2SSAOptimizer- /Ob3"
set "DEFAULT_LINKFLAGS=/emittoolversioninfo:no /NOCOFFGRPINFO /MERGE:.edata=.rdata /MERGE:.pdata=.rdata /d2:-ltcgNoDiff /FIXED"
set "DEFAULT_JOBS=%NUMBER_OF_PROCESSORS%"
if not defined DEFAULT_JOBS set "DEFAULT_JOBS=1"

REM Optional overrides:
REM   set DM40_PYTHON=py -3.13
REM   set DM40_OUT_DIR=build\ci\nuitka
REM   set DM40_CCFLAGS=/O2 /GL
REM   set DM40_LINKFLAGS=/LTCG
REM   set DM40_MODE_FLAGS=--deployment
REM   set DM40_CONSOLE_MODE=disable
REM   set DM40_MSVC=latest
REM   set DM40_JOBS=8
REM   set DM40_EMIT_MODULE_REPORTS=0
REM   set DM40_NUITKA_FLAGS=...

set "CL="
set "LINK="

set "PYTHON=%DEFAULT_PYTHON%"
if defined DM40_PYTHON set "PYTHON=%DM40_PYTHON%"

set "OUT_DIR=%DEFAULT_OUT_DIR%"
if defined DM40_OUT_DIR set "OUT_DIR=%DM40_OUT_DIR%"

set "MODE_FLAGS=%DEFAULT_MODE_FLAGS%"
if defined DM40_MODE_FLAGS set "MODE_FLAGS=%DM40_MODE_FLAGS%"

set "CONSOLE_MODE=%DEFAULT_CONSOLE_MODE%"
if defined DM40_CONSOLE_MODE set "CONSOLE_MODE=%DM40_CONSOLE_MODE%"

set "MSVC=%DEFAULT_MSVC%"
if defined DM40_MSVC set "MSVC=%DM40_MSVC%"

set "JOBS=%DEFAULT_JOBS%"
if defined DM40_JOBS set "JOBS=%DM40_JOBS%"

if defined CI (
  set "EMIT_MODULE_REPORTS=0"
) else (
  set "EMIT_MODULE_REPORTS=1"
)
if defined DM40_EMIT_MODULE_REPORTS set "EMIT_MODULE_REPORTS=%DM40_EMIT_MODULE_REPORTS%"

if /I "%EMIT_MODULE_REPORTS%"=="1" (
  set "REPORT_FLAGS=--report=%OUT_DIR%\compilation-report.xml --show-modules --show-modules-output=%OUT_DIR%\modules.txt"
) else if /I "%EMIT_MODULE_REPORTS%"=="0" (
  set "REPORT_FLAGS="
) else (
  echo ERROR: DM40_EMIT_MODULE_REPORTS must be 0 or 1. Got: %EMIT_MODULE_REPORTS%
  endlocal & exit /b 1
)

set "EXTRA_NUITKA_FLAGS="
if defined DM40_NUITKA_FLAGS set "EXTRA_NUITKA_FLAGS=%DM40_NUITKA_FLAGS%"

set "CCFLAGS=%DEFAULT_CCFLAGS%"
if defined DM40_CCFLAGS set "CCFLAGS=%CCFLAGS% %DM40_CCFLAGS%"

set "LINKFLAGS=%DEFAULT_LINKFLAGS%"
if defined DM40_LINKFLAGS set "LINKFLAGS=%LINKFLAGS% %DM40_LINKFLAGS%"
set "LINK=%LINKFLAGS%"

REM Preflight checks.
%PYTHON% --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python command failed: %PYTHON%
  endlocal & exit /b 1
)

%PYTHON% -m nuitka --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Nuitka is not available in the selected Python environment.
  echo        Install with: %PYTHON% -m pip install --upgrade nuitka
  endlocal & exit /b 1
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
if errorlevel 1 (
  echo ERROR: Failed to create output directory: %OUT_DIR%
  endlocal & exit /b 1
)

echo Running DM40 release build...
echo.
echo [build vars]
echo PYTHON=%PYTHON%
echo OUT_DIR=%OUT_DIR%
echo MODE_FLAGS=%MODE_FLAGS%
echo CONSOLE_MODE=%CONSOLE_MODE%
echo MSVC=%MSVC%
echo JOBS=%JOBS%
echo CCFLAGS=%CCFLAGS%
echo LINKFLAGS=%LINKFLAGS%
echo EXTRA_NUITKA_FLAGS=%EXTRA_NUITKA_FLAGS%

call :compile_shim ctypes || (endlocal & exit /b 1)

%PYTHON% -m nuitka main.py ^
  --standalone ^
  --onefile ^
  --output-filename=DM40GUI.exe ^
  --msvc=%MSVC% ^
  --assume-yes-for-downloads ^
  --enable-plugin=tk-inter ^
  --disable-plugin=multiprocessing ^
  --output-dir=%OUT_DIR% ^
  --lto=yes ^
  --jobs=%JOBS% ^
  %MODE_FLAGS% ^
  --experimental=eliminate-backports ^
  --experimental=deferred-annotations ^
  --experimental=winlibs-new ^
  --experimental=del_optimization ^
  --experimental=new-code-objects ^
  --python-flag=no_asserts ^
  --python-flag=no_docstrings ^
  --python-flag=isolated ^
  --include-module=_ctypes ^
  --include-windows-runtime-dlls=no ^
  --windows-console-mode=%CONSOLE_MODE% ^
  --noinclude-pytest-mode=nofollow ^
  --noinclude-setuptools-mode=nofollow ^
  --noinclude-unittest-mode=nofollow ^
  --noinclude-pydoc-mode=nofollow ^
  --noinclude-IPython-mode=nofollow ^
  --noinclude-dask-mode=nofollow ^
  --noinclude-numba-mode=nofollow ^
  --nofollow-import-to=ctypes,ctypes.wintypes,ctypes._endian,struct,threading ^
  --nofollow-import-to=queue,_queue,_threading_local ^
  --nofollow-import-to=_zstd,compression,compression._common,compression._common._streams ^
  --nofollow-import-to=compression.bz2,compression.gzip,compression.lzma,compression.zlib ^
  --nofollow-import-to=compression.zstd,compression.zstd._zstdfile ^
  --nofollow-import-to=bz2,_bz2,lzma,_lzma,gzip,_compression ^
  --nofollow-import-to=encodings.bz2_codec,encodings.base64_codec,encodings.hex_codec ^
  --nofollow-import-to=encodings.rot_13,encodings.punycode,encodings.idna ^
  --nofollow-import-to=ssl,_ssl,_socket,ipaddress,ftplib,imaplib,poplib ^
  --nofollow-import-to=http,email,urllib,urllib.parse,socketserver ^
  --nofollow-import-to=xmlrpc,xmlrpc.client,mimetypes ^
  --nofollow-import-to=selectors,select,subprocess ^
  --nofollow-import-to=argparse,pdb,doctest,cmd,code,codeop,difflib,trace ^
  --nofollow-import-to=traceback,tracemalloc,pstats,timeit ^
  --nofollow-import-to=modulefinder,pyclbr,py_compile,pickletools,symtable ^
  --nofollow-import-to=_ast_unparse,_py_warnings ^
  --nofollow-import-to=json,json.decoder,json.encoder,json.scanner ^
  --nofollow-import-to=pickle,_compat_pickle,tomllib,base64 ^
  --nofollow-import-to=tarfile,zipfile,zipfile._path ^
  --nofollow-import-to=xml,html,_markupbase ^
  --nofollow-import-to=tools,multiprocessing,_multiprocessing,concurrent.futures.process ^
  --nofollow-import-to=hashlib,_hashlib,_uuid,uuid ^
  --nofollow-import-to=_pyrepl,_sitebuiltins,_colorize ^
  --nofollow-import-to=builtins,__future__,__hello__,__phello__ ^
  --nofollow-import-to=datetime,_strptime,_pydatetime,calendar ^
  --nofollow-import-to=_pylong,bisect,unicodedata,signal ^
  --nofollow-import-to=warnings,logging,tempfile,_pyio ^
  --nofollow-import-to=_aix_support,_py_abc,contextvars ^
  --nofollow-import-to=_android_support,_apple_support,_osx_support ^
  --nofollow-import-to=webbrowser,configparser,gettext,graphlib ^
  --nofollow-import-to=importlib,importlib.metadata,importlib.resources ^
  --nofollow-import-to=importlib.simple,importlib.abc,importlib.readers ^
  --nofollow-import-to=typing,typing_extensions,dataclasses,copy ^
  --nofollow-import-to=statistics,fractions,decimal,numbers ^
  --nofollow-import-to=colorsys,fnmatch,sched,stringprep ^
  --nofollow-import-to=filecmp,fileinput,getopt,glob ^
  --nofollow-import-to=rlcompleter,netrc,pprint,nturl2path ^
  --nofollow-import-to=shlex,shutil,heapq,itertools ^
  --nofollow-import-to=pkgutil,platform,sysconfig,_wmi ^
  --nofollow-import-to=pathlib,pathlib._abc,pathlib._local,posixpath ^
  --nofollow-import-to=string,sre_compile,sre_constants,sre_parse ^
  --nofollow-import-to=tkinter.test,tkinter.tix,tkinter.dnd ^
  --nofollow-import-to=tkinter.commondialog,tkinter.messagebox ^
  --nofollow-import-to=idlelib,turtledemo ^
  --noinclude-data-files=tk/images/** ^
  --noinclude-data-files=tk/msgs/** ^
  --noinclude-data-files=tk/dialog.tcl ^
  --noinclude-data-files=tk/msgbox.tcl ^
  --noinclude-data-files=tk/choosedir.tcl ^
  --noinclude-data-files=tk/clrpick.tcl ^
  --noinclude-data-files=tk/comdlg.tcl ^
  --noinclude-data-files=tk/fontchooser.tcl ^
  --noinclude-data-files=tk/tkfbox.tcl ^
  --noinclude-data-files=tk/xmfbox.tcl ^
  --noinclude-data-files=tk/license.terms ^
  --noinclude-data-files=tk/console.tcl ^
  --noinclude-data-files=tk/unsupported.tcl ^
  --noinclude-data-files=tk/obsolete.tcl ^
  --noinclude-data-files=tk/mkpsenc.tcl ^
  --noinclude-data-files=tk/iconlist.tcl ^
  --noinclude-data-files=tk/megawidget.tcl ^
  --noinclude-data-files=tk/optMenu.tcl ^
  --noinclude-data-files=tk/tearoff.tcl ^
  --noinclude-data-files=tk/safetk.tcl ^
  --noinclude-data-files=tk/ttk/aquaTheme.tcl ^
  --noinclude-data-files=tcl/msgs/** ^
  --noinclude-data-files=tcl/opt0.4/** ^
  --noinclude-data-files=tcl/http1.0/** ^
  --noinclude-data-files=tcl/tzdata/** ^
  --noinclude-data-files=tcl/history.tcl ^
  --noinclude-data-files=tcl/parray.tcl ^
  --noinclude-data-files=tcl/word.tcl ^
  --noinclude-data-files=tcl/clock.tcl ^
  --noinclude-data-files=tcl/safe.tcl ^
  --noinclude-data-files=tcl8/**/msgcat-*.tm ^
  --noinclude-data-files=tcl8/8.5/tcltest-2.5.8.tm ^
  --noinclude-data-files=tcl8/8.6/http-2.9.8.tm ^
  --noinclude-data-files=tcl8/8.4/platform-1.0.19.tm ^
  --noinclude-data-files=tcl8/8.4/platform/shell-1.1.4.tm ^
  --noinclude-data-files=tcl/encoding/big5.enc ^
  --noinclude-data-files=tcl/encoding/cns11643.enc ^
  --noinclude-data-files=tcl/encoding/cp932.enc ^
  --noinclude-data-files=tcl/encoding/cp936.enc ^
  --noinclude-data-files=tcl/encoding/cp949.enc ^
  --noinclude-data-files=tcl/encoding/cp950.enc ^
  --noinclude-data-files=tcl/encoding/euc-cn.enc ^
  --noinclude-data-files=tcl/encoding/euc-jp.enc ^
  --noinclude-data-files=tcl/encoding/euc-kr.enc ^
  --noinclude-data-files=tcl/encoding/gb1988.enc ^
  --noinclude-data-files=tcl/encoding/gb2312.enc ^
  --noinclude-data-files=tcl/encoding/gb2312-raw.enc ^
  --noinclude-data-files=tcl/encoding/gb12345.enc ^
  --noinclude-data-files=tcl/encoding/jis0201.enc ^
  --noinclude-data-files=tcl/encoding/jis0208.enc ^
  --noinclude-data-files=tcl/encoding/jis0212.enc ^
  --noinclude-data-files=tcl/encoding/ksc5601.enc ^
  --noinclude-data-files=tcl/encoding/shiftjis.enc ^
  --noinclude-data-files=tcl/encoding/tis-620.enc ^
  --noinclude-data-files=tcl/encoding/dingbats.enc ^
  --noinclude-data-files=tcl/encoding/ebcdic.enc ^
  --noinclude-data-files=tcl/encoding/symbol.enc ^
  --noinclude-data-files=tcl/encoding/iso2022*.enc ^
  --noinclude-data-files=tcl/encoding/iso8859-*.enc ^
  --noinclude-data-files=tcl/encoding/koi8*.enc ^
  --noinclude-data-files=tcl/encoding/mac*.enc ^
  %REPORT_FLAGS% %EXTRA_NUITKA_FLAGS%

if errorlevel 1 (
  echo.
  echo Build failed.
  endlocal & exit /b %errorlevel%
)

echo.
echo Build complete.
echo Output: %OUT_DIR%
endlocal & exit /b 0

:compile_shim
set "SHIM_NAME=%~1"
%PYTHON% -c "import py_compile; py_compile.compile('shims/%SHIM_NAME%_shim.py', 'shims/%SHIM_NAME%.pyc', doraise=True, optimize=2)"
if errorlevel 1 (
  echo ERROR: Failed to compile shims/%SHIM_NAME%_shim.py to .pyc
  exit /b 1
)
exit /b 0
