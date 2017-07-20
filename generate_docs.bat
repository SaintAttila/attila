@ECHO OFF
REM See http://www.sphinx-doc.org/en/stable/man/sphinx-apidoc.html

pip install Sphinx
sphinx-apidoc -d 3 -e -f -F -H "Saint Attila" -A "Aaron Hosford" -V 0.0 -o doc/sphinx attila
cd doc/sphinx

REM We have to run it indirectly via Python because make somehow closes cmd.exe otherwise, which
REM prevents the remaining commands from executing.
python -c "import os; os.system('make html')"

cd ..\..
start doc/sphinx/_build/html/index.html

pandoc -f markdown -t html doc\attila.md -o doc\attila.html
pandoc -f markdown -t latex doc\attila.md -o doc\attila.pdf
