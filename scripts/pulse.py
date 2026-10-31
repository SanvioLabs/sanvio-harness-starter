#!/usr/bin/env python3
"""A team's daily multiple-choice question, kept in a shared synced folder.

    python3 scripts/pulse.py check                                   # is the bank well formed?
    python3 scripts/pulse.py question [--date YYYY-MM-DD] [--json]   # the day's question
    python3 scripts/pulse.py answer <id> <number> [--date YYYY-MM-DD]
    python3 scripts/pulse.py answer <id> --other-file <path> [--date YYYY-MM-DD]
    python3 scripts/pulse.py results [--date YYYY-MM-DD]             # counts for a day, yesterday by default

The folder comes from HARNESS_PULSE_FOLDER. It holds questions.md, the bank, and
answers/<login>.jsonl, one file per person. Only `answer` writes, and only to
that person's file. skills/pulse/ is the procedure and says who may read what.
Refusals and problems go to stderr with exit 1, and success goes to stdout.
"""
import argparse
import collections
import datetime
import getpass
import json
import os
import re
import sys

BANK = "questions.md"
ANSWERS = "answers"
OTHER = "Other"
MAX_CHIP = 12
MIN_OPTIONS = 2
MAX_OPTIONS = 4
MIN_TO_SHOW = 3
QUESTION_ID = re.compile(r"[a-z0-9-]+")
NUMBER = re.compile(r"[0-9]+")
PERSON_FILE = re.compile(r"[A-Za-z0-9._-]+\.jsonl")
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")  # the same pattern as .claude/hooks/usage_log.py, copied
HOW_TO_SET = 'Set it in your shell profile: export HARNESS_PULSE_FOLDER="/path/to/the/shared/folder"'


class Refused(Exception):
    """A one-line reason to stop, having written nothing."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        print("pulse: {}".format(message), file=sys.stderr)
        sys.exit(1)


def pulse_folder():
    folder = os.environ.get("HARNESS_PULSE_FOLDER", "")
    if not folder:
        raise Refused("HARNESS_PULSE_FOLDER isn't set. " + HOW_TO_SET)
    if not os.path.isdir(folder):
        raise Refused("HARNESS_PULSE_FOLDER names a folder that doesn't exist: {}. {}".format(folder, HOW_TO_SET))
    return folder


def parse_bank(text):
    """The questions in file order. Anything that isn't part of a question is ignored."""
    questions = []
    current = None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## "):
            current = {"id": line[3:].strip(), "chip": "", "question": "", "options": []}
            questions.append(current)
        elif current is None:
            continue
        elif line.startswith("Chip:"):
            current["chip"] = line[len("Chip:"):].strip()
        elif line.startswith("Question:"):
            current["question"] = line[len("Question:"):].strip()
        elif line.startswith("- "):
            label, _, description = line[2:].partition(":")
            current["options"].append((label.strip(), description.strip()))
    return questions


def bank_problems(questions):
    """Every problem in the bank, one line each, each starting with its question's id."""
    if not questions:
        return ["{}: it has no questions".format(BANK)]
    found = []
    seen = set()
    for question in questions:
        name = question["id"] or "(no id)"
        if not QUESTION_ID.fullmatch(question["id"]):
            found.append("{}: the id must be lowercase letters, digits and hyphens".format(name))
        if question["id"] in seen:
            found.append("{}: two questions have this id".format(name))
        seen.add(question["id"])
        if not question["chip"]:
            found.append("{}: the chip is missing or empty".format(name))
        elif len(question["chip"]) > MAX_CHIP:
            found.append("{}: the chip is over {} characters".format(name, MAX_CHIP))
        if not question["question"]:
            found.append("{}: the question is missing or empty".format(name))
        options = question["options"]
        if len(options) < MIN_OPTIONS:
            found.append("{}: it has fewer than {} options".format(name, MIN_OPTIONS))
        elif len(options) > MAX_OPTIONS:
            found.append("{}: it has more than {} options".format(name, MAX_OPTIONS))
        labels = collections.Counter(label for label, _ in options)
        for place, (label, description) in enumerate(options, 1):
            if not label:
                found.append("{}: option {} has no label".format(name, place))
            if not description:
                found.append("{}: option {} has no description".format(name, place))
            if label == OTHER:
                found.append("{}: an option is labelled {}, which the window adds itself".format(name, OTHER))
        for label, count in labels.items():
            if label and count > 1:
                found.append("{}: two options have the label {}".format(name, label))
    return found


def read_bank(folder):
    """(questions, problems) for the bank in this folder."""
    path = os.path.join(folder, BANK)
    if not os.path.isfile(path):
        return [], ["{}: there is no {} in the folder".format(BANK, BANK)]
    try:
        with open(path, "rb") as bank:
            text = bank.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], ["{}: it isn't valid UTF-8".format(BANK)]
    except OSError as error:
        return [], ["{}: it can't be read ({})".format(BANK, error.strerror)]
    questions = parse_bank(text)
    return questions, bank_problems(questions)


def chosen_day(value, default):
    if value is None:
        return default
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise Refused("--date must be a real date written YYYY-MM-DD, not {}".format(value))


def day_question(questions, day):
    return questions[day.toordinal() % len(questions)]


def login_name():
    return SAFE_NAME.sub("_", getpass.getuser()) or "unknown"


def parse_answer_line(raw):
    """The record on this line of an answers file, or None if the line doesn't count."""
    try:
        record = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):  # undecodable bytes are a ValueError too
        return None
    if not isinstance(record, dict):
        return None
    for key in ("date", "id", "answer"):
        value = record.get(key)
        if not isinstance(value, str) or not value:
            return None
    return record


def read_answers(path):
    """(records, how many lines were skipped) for one person's file."""
    with open(path, "rb") as answers:
        lines = answers.read().split(b"\n")
    if not lines[-1]:
        lines.pop()
    records = [parse_answer_line(raw) for raw in lines]
    kept = [record for record in records if record is not None]
    return kept, len(records) - len(kept)


def my_last_answer(folder, day, question_id):
    path = os.path.join(folder, ANSWERS, login_name() + ".jsonl")
    if not os.path.isfile(path):
        return None
    answered = None
    for record in read_answers(path)[0]:
        if record["date"] == day.isoformat() and record["id"] == question_id:
            answered = record["answer"]
    return answered


def run_check(folder, questions, args):
    count = len(questions)
    print("{}: {} question{}, no problems.".format(BANK, count, "" if count == 1 else "s"))
    return 0


def run_question(folder, questions, args):
    day = chosen_day(args.date, datetime.date.today())
    question = day_question(questions, day)
    if args.json:
        print(json.dumps({
            "date": day.isoformat(),
            "id": question["id"],
            "answered": my_last_answer(folder, day, question["id"]),
            "question": {
                "question": question["question"],
                "header": question["chip"],
                "multiSelect": False,
                "options": [{"label": label, "description": description}
                            for label, description in question["options"]],
            },
        }))
        return 0
    # The id is here too because `answer` takes it.
    print("{} ({})".format(day.isoformat(), question["id"]))
    print(question["chip"])
    print(question["question"])
    for place, (label, description) in enumerate(question["options"], 1):
        print("{}. {}: {}".format(place, label, description))
    return 0


def read_other_file(path):
    try:
        with open(path, "rb") as other:
            text = other.read().decode("utf-8").strip()
    except OSError as error:
        raise Refused("--other-file can't be read: {}".format(error.strerror))
    except UnicodeDecodeError:
        raise Refused("--other-file isn't valid UTF-8")
    if not text:
        raise Refused("--other-file is empty")
    return text


def run_answer(folder, questions, args):
    today = datetime.date.today()
    day = chosen_day(args.date, today)
    question = next((q for q in questions if q["id"] == args.id), None)
    if question is None:
        raise Refused("{} isn't in the bank".format(args.id))
    if args.date is None and question is not day_question(questions, today):
        raise Refused("{} isn't today's question. Use --date for a day you missed".format(args.id))
    if day > today:
        raise Refused("--date is after today: {}".format(day.isoformat()))
    if (args.number is None) == (args.other_file is None):
        raise Refused("give one of an option's number or --other-file")
    record = {"date": day.isoformat(), "id": question["id"]}
    if args.other_file is not None:
        record["answer"] = OTHER
        record["other"] = read_other_file(args.other_file)
    else:
        places = [str(place) for place in range(1, len(question["options"]) + 1)]
        if not NUMBER.fullmatch(args.number) or args.number not in places:
            raise Refused("{} isn't one of that question's options: 1 to {}".format(args.number, len(places)))
        record["answer"] = question["options"][int(args.number) - 1][0]
    answers = os.path.join(folder, ANSWERS)
    os.makedirs(answers, exist_ok=True)
    with open(os.path.join(answers, login_name() + ".jsonl"), "a", encoding="utf-8") as out:
        out.write(json.dumps(record, ensure_ascii=False) + "\n")
    print("Recorded {} for {} on {}.".format(record["answer"], record["id"], record["date"]))
    return 0


def tally(folder, day):
    """({question id: each person's last label}, files skipped, lines skipped) for one date."""
    picks = {}
    files = lines = 0
    answers = os.path.join(folder, ANSWERS)
    if not os.path.isdir(answers):
        return picks, files, lines
    for name in sorted(os.listdir(answers)):
        path = os.path.join(answers, name)
        if not PERSON_FILE.fullmatch(name) or not os.path.isfile(path):
            files += 1
            continue
        try:
            records, bad = read_answers(path)
        except OSError:
            files += 1
            continue
        lines += bad
        last = {record["id"]: record["answer"] for record in records if record["date"] == day}
        for question_id, label in last.items():
            picks.setdefault(question_id, []).append(label)
    return picks, files, lines


def counted(count, noun):
    return "{} {}{}".format(count, noun, "" if count == 1 else "s")


def run_results(folder, questions, args):
    day = chosen_day(args.date, datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    picks, files, lines = tally(folder, day)
    bank = {question["id"]: question for question in questions}
    print("Results for {}".format(day))
    order = [question["id"] for question in questions if question["id"] in picks]
    order += sorted(question_id for question_id in picks if question_id not in bank)
    if not order:
        print("No answers for this date.")
    for question_id in order:
        question = bank.get(question_id)
        heading = question["chip"] if question else question_id
        labels = picks[question_id]
        if len(labels) < MIN_TO_SHOW:
            print("{}: fewer than three answered.".format(heading))
            continue
        print("{}: {} answered".format(heading, len(labels)))
        counts = collections.Counter(labels)
        if question:
            shown = [label for label, _ in question["options"]] + [OTHER]
            shown += sorted(set(counts) - set(shown))
        else:
            shown = sorted(counts)
        for label in shown:
            print("  {}: {}".format(label, counts[label]))
    print("Skipped {} and {}.".format(counted(files, "file"), counted(lines, "line")))
    return 0


def build_parser():
    parser = Parser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="list each problem in the bank")
    question = commands.add_parser("question", help="print the day's question")
    question.add_argument("--date", help="another day, YYYY-MM-DD")
    question.add_argument("--json", action="store_true", help="print JSON instead of text")
    answer = commands.add_parser("answer", help="record your answer in the shared folder")
    answer.add_argument("id", help="the question's id")
    answer.add_argument("number", nargs="?", help="the option's place, from 1")
    answer.add_argument("--other-file", help="a file holding your own words, in place of a number")
    answer.add_argument("--date", help="another day, YYYY-MM-DD")
    results = commands.add_parser("results", help="print the counts for a day, yesterday by default")
    results.add_argument("--date", help="another day, YYYY-MM-DD")
    return parser


COMMANDS = {"check": run_check, "question": run_question, "answer": run_answer, "results": run_results}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = build_parser().parse_args(argv)
    try:
        folder = pulse_folder()
        questions, problems = read_bank(folder)
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1
        return COMMANDS[args.command](folder, questions, args)
    except Refused as refusal:
        print(refusal, file=sys.stderr)
    except OSError as error:
        print("pulse: {}".format(error), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
