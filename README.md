# Anki deck reorder

This is a simple command line script that tries to optimize the order of the cards in your Anki deck, when you are learning foreign languages.
It requires the cards to have two fields, one for the word in the foreign language and one for a sentence that uses this word.
Then, the script tries to reorganize the cards in such a way that whenever you get a new card, it is more likely that you have already learned the words used in the sentence of this card (except for the new word, of course). Perfect ordering is impossible due to stuff like cyclical dependencies, but the result is better than a random ordering.

## How do I use this?

1. Download/extract an .apkg file
2. Run this script with `python3 script.py mypack.apkg mypack_ordered.apkg`
3. Tell the script which fields contain the foreign word and the sentence (you will be prompted for this)
4. Import the new .apkg file into Anki
5. Enjoy!

## Dependencies
This script uses argparse, sqlite3 and zipfile, all of which are included in the Python standard library, so you shouldnt need to install any libraries.
If you however encounter any issues, you can use [Poetry](https://python-poetry.org/) to create a virtual environment by running `poetry install && poetry shell`.

Enjoy!