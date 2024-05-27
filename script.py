import argparse
from collections import defaultdict
import json
import os
import sqlite3
import tempfile
import time
from typing import Any
import zipfile


FIELDNAME = "Redkinda's Learn Order"


def prompt_select(question: str, options: list[tuple[str, str]]) -> str:
    print(question)
    for i, pair in enumerate(options):
        print(f"{i+1}. {pair[1]}")
    while True:
        try:
            selected = int(input("Select: "))
            if selected < 1 or selected > len(options):
                print("Invalid selection")
                continue

            print("")
            return options[selected - 1][0]
        except ValueError:
            print("Invalid selection")


def reoder(input_file: str, output_file: str):
    # create a temp folder
    tmpfolder = tempfile.mkdtemp(prefix="anki_reorder_")
    # unzip apkg file into that directory
    zipfile.ZipFile(input_file).extractall(tmpfolder)

    conn = sqlite3.connect(database=f"{tmpfolder}/collection.anki2")
    cursor = conn.cursor()

    models = cursor.execute("select models from col;").fetchone()
    # if there is already a field with FIELDNAME, we exit
    models = json.loads(models[0])

    if len(models) > 1:
        print("Multiple models found, please select one:")
        selected_model = prompt_select("Select model to reorder", sorted(list({(model_id, model["name"]) for model_id, model in models.items()})))
        model = models[selected_model]
    elif len(models) == 1:
        model = list(models.values())[0]
        print(f"Using model '{model['name']}'")

    for fld in model["flds"]:
        if fld["name"] == FIELDNAME:
            print(f"Collection is already reordered - exiting")
            exit(1)

    # select random note
    random_note_flds = (
        cursor.execute("select flds from notes limit 1;").fetchone()[0].split("\x1f")
    )
    field_names = [
        (fld["name"], f"{fld["name"]} - {fld_example}") for fld, fld_example in zip(model["flds"], random_note_flds)
    ]
    # we need to prompt user to select the field with single word to learn
    selected_field_word = prompt_select("Which field is the word in foreign language?", field_names)
    selected_field_sentence = prompt_select("Which field is the sentence in foreign language?", field_names)

    word_index = next(i for i, fld in enumerate(model["flds"]) if fld["name"] == selected_field_word)
    sentence_index = next(i for i, fld in enumerate(model["flds"]) if fld["name"] == selected_field_sentence)


    destemmed = defaultdict(set)
    word_ids = dict()
    skipped_words = []
    cards = {}

    learn_dependencies = defaultdict(set)

    # select * from notes limit 1;
    rows = cursor.execute("select * from notes;").fetchall()
    for row in rows:
        flds = row[6].lower()
        note_id: str = row[0]

        flds = flds.split("\x1f")
        learned_word = flds[word_index]
        destemmed[learned_word].add((flds[1], note_id))

        foreign_text = flds[sentence_index]
        dependencies = set()
        for word in foreign_text.split(" "):
            # strip punctuation
            word = word.strip(".,()[]{}:;!?'\"•-_ ")
            if word == "":
                continue
            word = word
            if word == learned_word:
                continue
            dependencies.add(word)

        if learned_word in learn_dependencies:
            print(
                f"Duplicate learned word - skipping {learned_word} - {destemmed[learned_word]}"
            )
            skipped_words.append(learned_word)
            continue

        word_ids[learned_word] = note_id
        cards[learned_word] = flds
        learn_dependencies[learned_word] = dependencies

    # remove all dependencies that are not in learn_dependencies - we cant learn them from this deck
    for learned_word, dependencies in learn_dependencies.items():
        learn_dependencies[learned_word] = {
            dep for dep in dependencies if dep in learn_dependencies
        }

    dependees = defaultdict(set)
    for learned_word, dependencies in learn_dependencies.items():
        for dependency in dependencies:
            dependees[dependency].add(learned_word)

    new_order = []

    while len(learn_dependencies) > 0:
        # we select a word from learn_dependencies with least dependencies
        # if there are multiple of same amount, we select one with most dependees

        # min_deps = float("inf")
        # selected_word = None
        # for learned_word, dependencies in learn_dependencies.items():
        #     if len(dependencies) < min_deps:
        #         min_deps = len(dependencies)
        #         selected_word = learned_word
        #     elif len(dependencies) == min_deps:
        #         if len(dependees[learned_word]) > len(dependees[selected_word]):
        #             selected_word = learned_word

        # alternative strategy - we give card a score based on dependee_count - dependency_count * 10
        max_score = float("-inf")
        selected_word = None
        for learned_word, dependencies in learn_dependencies.items():
            score = len(dependees[learned_word]) - len(dependencies) * 10
            if score > max_score:
                max_score = score
                selected_word = learned_word

        # we have a selected word! pop it from dependencies and dependees
        print(
            f"Selected word: {selected_word} - {len(learn_dependencies[selected_word])} / {len(dependees[selected_word])}"
        )
        new_order.append(selected_word)
        for dep in dependees[selected_word]:
            learn_dependencies[dep].discard(selected_word)

        del learn_dependencies[selected_word]

        for dep in dependees[selected_word]:
            if dep == selected_word:
                continue
            dependees[dep].discard(selected_word)

        del dependees[selected_word]

    print(new_order)

    updated_note_ids = set()
    i = 1
    for learned_word in new_order:
        maps = destemmed[learned_word]
        for m in maps:
            note_id = m[1]
            order_id = str(i)
            # update flds to replace old sfld with new sfld
            # flds is a long string, we replace the relevant part only
            old_flds = cursor.execute(
                f"select flds from notes where id = ?;", (note_id,)
            ).fetchone()
            if old_flds is None:
                print(f"Skipping {note_id} - not found")
                continue

            if note_id in updated_note_ids:
                print(f"Skipping {note_id} - already updated")
                continue

            updated_note_ids.add(note_id)
            old_flds = old_flds[0]
            new_flds = old_flds + chr(0x1F) + order_id

            # updat flds
            cursor.execute(
                "update notes set flds = ?, sfld = ? where id = ?;",
                (new_flds, order_id, note_id),
            )

            # update both sfld and flds
            # cursor.execute(
            #     "update notes set sfld = ?, flds = ? where sfld = ?;",
            #     (new_sfld, new_flds, old_sfld),
            # )
            i += 1

    # add FIELDNAME field to models
    models = cursor.execute("select models from col;").fetchone()
    models = json.loads(models[0])
    for model_id, model in models.items():
        model["sortf"] = len(model["flds"])
        model["flds"].append(
            dict(
                name=FIELDNAME,
                ord=len(model["flds"]),
                sticky=False,
                rtl=False,
                font="Arial",
                size=20,
                description="",
            ),
        )

    # update col models
    cursor.execute(
        "update col set models = ?",
        (json.dumps(models),),
    )

    cursor.execute("update col set mod = ?;", (int(time.time()),))

    conn.commit()
    conn.close()

    print(f"Done updating, creating package at {output_file}")

    # now zip the folder back
    with zipfile.ZipFile(output_file, "w") as zf:
        for root, dirs, files in os.walk(tmpfolder):
            for file in files:
                zf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), tmpfolder),
                )

    print("Done!")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help=".apkg input file location")
    parser.add_argument("output", help=".apkg output file location")

    args = parser.parse_args()
    reoder(args.input, args.output)


if __name__ == "__main__":
    main()
