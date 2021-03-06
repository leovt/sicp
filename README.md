# Structure and Interpretation of Computer Programs

Project to produce an epub from the open book at
https://mitpress.mit.edu/sites/default/files/sicp/index.html

# Download the book
The book can be downloaded from the github release: https://github.com/leovt/sicp/releases/download/v1.1/sicp.epub

# Licensing

## Licensing of the book
Structure and Interpretation of Computer Programs by Harold Abelson and Gerald Jay Sussman with Julie Sussman 
is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License by the MIT Press. 

The modifications and additions to the work above located in the new_contents folder are licensed under the 
Creative Commons Attribution-ShareAlike 4.0 International License by Leonhard Vogt

The EPub which is produced by the scripts in this repository is a derivative work of the above mentioned book.
It is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License. 

To view a copy of this license, visit http://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

## Licensing of the program code
The program code used to produce the EPub version of the book is licensed under the MIT license (see the file LICENSE)

# Modifications to the book
The html markup has been modified in order to be used in the EPub format.
The css stylesheet has been replaced.
These modifications should not alter the content, but will affect presentation.

Tables of Content have been added according to the EPub file format.

# Changelog

## v1.1
* Set a reasonable size for images
* Improved cover page
* Replace quotes and dashes with typograpical unicode symbols
* Remove comments

# Notes
MathML has not been used on purpose as some EPub reading devices do not support MathML and provide illegible equations.
So far some symbols have been replaced by unicode charactes, displayed equation remain in the image format of the original source. 

Much of the python code is very specific to this particular e-book. In a later stage I might separate the general parts from the specific parts.
