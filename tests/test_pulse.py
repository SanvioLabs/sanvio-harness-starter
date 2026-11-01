"""Run with: python3 -m unittest discover -s tests"""
import ast
import datetime
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pulse.py"
SKILL = ROOT / "skills" / "pulse" / "SKILL.md"
GUIDE = ROOT / "skills" / "pulse" / "README.md"
EXAMPLE = ROOT / "skills" / "pulse" / "questions.example.md"
STANDUP = ROOT / "skills" / "standup" / "SKILL.md"
CLEARED = ("A source is cleared only when its `Cleared for this tool` cell in `company/DATA.md` is exactly "
           "`yes`, ignoring case and surrounding spaces. Anything else isn't cleared: `no`, `unconfirmed`, "
           "blank, `yes` followed by anything (such as `yes, summaries only`), or no row.")
STDLIB = {"argparse", "collections", "datetime", "getpass", "json", "os", "re", "sys"}

BANK = """# Team pulse

Some prose, and a line that isn't an option yet:
- Stray: before the first heading
Chip: Stray
### not-a-heading

## alpha
Chip: Alpha chip
Question: How is alpha?

- Good: It went well
- Bad: It went badly

## beta
Chip: Beta chip
Question: How is beta?
- Up: Going up
- Flat: Staying flat
- Down: Going down

## gamma
Chip: Gamma chip
Question: How is gamma?
- Yes: It is
- No: It isn't
"""
IDS = ["alpha", "beta", "gamma"]
TWO_OPTIONS = "- One: First\n- Two: Second\n"


def question(body=TWO_OPTIONS, chip="Chip: Fine\n", ask="Question: Why?\n", heading="## one\n"):
    return heading + chip + ask + body


def flat(text):
    return " ".join(text.split())


class PulseCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.folder = self.tmp / "shared"
        self.folder.mkdir()
        self.today = datetime.date.today()
        self.yesterday = (self.today - datetime.timedelta(days=1)).isoformat()

    def pulse(self, *args, folder=None, unset=False, login="pat"):
        env = dict(os.environ)
        env.pop("HARNESS_PULSE_FOLDER", None)
        if not unset:
            env["HARNESS_PULSE_FOLDER"] = str(folder or self.folder)
        env["LOGNAME"] = login
        env["USER"] = login
        return subprocess.run([sys.executable, str(SCRIPT)] + list(args), env=env, capture_output=True,
                              encoding="utf-8", errors="replace", cwd=str(self.tmp))

    def bank(self, text=BANK):
        (self.folder / "questions.md").write_text(text, encoding="utf-8")

    def files(self):
        return sorted(p.relative_to(self.folder).as_posix() for p in self.folder.rglob("*"))

    def said(self, result):
        return flat(result.stdout + " " + result.stderr)

    def today_id(self):
        return IDS[self.today.toordinal() % len(IDS)]

    def not_today_id(self):
        return IDS[(self.today.toordinal() + 1) % len(IDS)]

    def assert_refused(self, result, before, *words):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.files(), before)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip(), "a refusal says why")
        for word in words:
            self.assertIn(word, self.said(result))

    def answers(self, name="pat"):
        path = self.folder / "answers" / (name + ".jsonl")
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def person(self, name, *records):
        answers = self.folder / "answers"
        answers.mkdir(exist_ok=True)
        lines = [r if isinstance(r, str) else json.dumps(r) for r in records]
        (answers / (name + ".jsonl")).write_text("".join(line + "\n" for line in lines), encoding="utf-8")

    def pick(self, question_id, label, date=None, **extra):
        record = {"date": date or self.yesterday, "id": question_id, "answer": label}
        record.update(extra)
        return record


class Folder(PulseCase):
    COMMANDS = (["check"], ["question"], ["answer", "alpha", "1"], ["results"])

    def test_unset_says_so_says_how_and_writes_nothing(self):
        self.bank()
        before = self.files()
        for command in self.COMMANDS:
            with self.subTest(command=command):
                result = self.pulse(*command, unset=True)
                self.assert_refused(result, before, "HARNESS_PULSE_FOLDER", "isn't set", "export")
                self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_a_folder_that_does_not_exist_says_so_and_is_not_created(self):
        missing = self.tmp / "nowhere"
        for command in self.COMMANDS:
            with self.subTest(command=command):
                result = self.pulse(*command, folder=missing)
                self.assertEqual(result.returncode, 1)
                self.assertIn("doesn't exist", self.said(result))
                self.assertIn("export", self.said(result))
                self.assertEqual(len(result.stderr.strip().splitlines()), 1)
                self.assertFalse(missing.exists())

    def test_the_folder_is_checked_before_the_command(self):
        result = self.pulse("question", "--date", "not-a-date", unset=True)
        self.assertIn("HARNESS_PULSE_FOLDER", self.said(result))
        self.assertNotIn("--date", self.said(result))


class BankProblems(PulseCase):
    CASES = {
        "id with capitals": (question(heading="## One\n"), "One:", "lowercase"),
        "id with a space": (question(heading="## one two\n"), "one two:", "lowercase"),
        "no chip": (question(chip=""), "one:", "chip"),
        "empty chip": (question(chip="Chip:   \n"), "one:", "chip"),
        "chip of 13": (question(chip="Chip: Thirteen char\n"), "one:", "12"),
        "no question": (question(ask=""), "one:", "question is missing"),
        "empty question": (question(ask="Question:\n"), "one:", "question is missing"),
        "empty label": (question("- : First\n- Two: Second\n"), "one:", "no label"),
        "empty description": (question("- One:\n- Two: Second\n"), "one:", "no description"),
        "no colon": (question("- One\n- Two: Second\n"), "one:", "no description"),
        "one option": (question("- One: First\n"), "one:", "fewer than 2"),
        "no options": (question(""), "one:", "fewer than 2"),
        "five options": (question("".join("- L{}: d\n".format(n) for n in range(5))), "one:", "more than 4"),
        "same label twice": (question("- One: First\n- One: Second\n"), "one:", "two options"),
        "option named Other": (question("- One: First\n- Other: Second\n"), "one:", "Other"),
        "same id twice": (question() + question(), "one:", "two questions"),
        "no questions": ("# Only a title\n\nSome prose.\n", "questions.md:", "no questions"),
    }

    def test_check_names_each_problem_and_exits_1_writing_nothing(self):
        for name, (text, where, words) in self.CASES.items():
            with self.subTest(name):
                self.bank(text)
                before = self.files()
                self.assert_refused(self.pulse("check"), before, where, words)

    def test_every_other_command_prints_the_same_problems_and_refuses(self):
        for name, (text, where, words) in self.CASES.items():
            self.bank(text)
            before = self.files()
            expected = self.pulse("check").stderr
            for command in (["question"], ["question", "--json"], ["answer", "one", "1"], ["results"]):
                with self.subTest(name, command=command):
                    result = self.pulse(*command)
                    self.assert_refused(result, before)
                    self.assertEqual(result.stderr, expected)

    def test_a_missing_bank_is_a_problem_for_every_command(self):
        for command in (["check"], ["question"], ["answer", "one", "1"], ["results"]):
            with self.subTest(command=command):
                self.assert_refused(self.pulse(*command), [], "questions.md:", "no questions.md")

    def test_undecodable_bytes_are_a_problem_not_a_traceback(self):
        (self.folder / "questions.md").write_bytes(b"## one\nChip: \xff\xfe\n")
        result = self.pulse("check")
        self.assert_refused(result, ["questions.md"], "questions.md:", "UTF-8")
        self.assertNotIn("Traceback", result.stderr)

    def test_every_problem_is_listed_not_just_the_first(self):
        self.bank(question(chip="", ask="") + question(heading="## TWO\n"))
        said = self.said(self.pulse("check"))
        for words in ("one: the chip", "one: the question", "TWO: the id"):
            self.assertIn(words, said)

    def test_a_good_bank_prints_its_count_and_exits_0(self):
        self.bank()
        result = self.pulse("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 questions", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_a_chip_of_exactly_12_passes(self):
        self.bank(question(chip="Chip: Twelve chars\n"))
        self.assertEqual(self.pulse("check").returncode, 0)

    def test_a_byte_order_mark_is_not_part_of_the_first_line(self):
        (self.folder / "questions.md").write_bytes(b"\xef\xbb\xbf" + question().encode("utf-8"))
        result = self.pulse("question", "--json", "--date", "2026-01-01")
        self.assertEqual(json.loads(result.stdout)["id"], "one")

    def test_what_is_not_part_of_a_question_is_ignored(self):
        self.bank()
        result = self.pulse("check")
        self.assertIn("3 questions", result.stdout)
        day = datetime.date(2026, 3, 2)
        day += datetime.timedelta(days=(0 - day.toordinal()) % 3)
        options = json.loads(self.pulse("question", "--json", "--date", day.isoformat()).stdout)
        self.assertEqual(options["id"], "alpha")
        self.assertEqual([o["label"] for o in options["question"]["options"]], ["Good", "Bad"])


class Question(PulseCase):
    def setUp(self):
        super().setUp()
        self.bank()

    def test_the_index_is_the_ordinal_modulo_the_count_in_file_order(self):
        start = datetime.date(2026, 5, 1)
        for offset in range(7):
            day = start + datetime.timedelta(days=offset)
            result = self.pulse("question", "--json", "--date", day.isoformat())
            self.assertEqual(json.loads(result.stdout)["id"], IDS[day.toordinal() % 3], day)

    def test_with_no_date_it_is_todays_local_date(self):
        data = json.loads(self.pulse("question", "--json").stdout)
        self.assertEqual(data["date"], self.today.isoformat())
        self.assertEqual(data["id"], self.today_id())

    def test_the_plain_text_has_date_chip_question_and_numbered_options(self):
        day = datetime.date(2026, 5, 1)
        day += datetime.timedelta(days=(1 - day.toordinal()) % 3)  # beta, the one with three options
        result = self.pulse("question", "--date", day.isoformat())
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertIn(day.isoformat(), lines[0])
        self.assertIn("beta", lines[0])
        self.assertEqual(lines[1:], ["Beta chip", "How is beta?", "1. Up: Going up", "2. Flat: Staying flat",
                                     "3. Down: Going down"])

    def test_json_is_exactly_the_shape_the_window_takes(self):
        day = datetime.date(2026, 5, 1)
        day += datetime.timedelta(days=(0 - day.toordinal()) % 3)
        result = self.pulse("question", "--json", "--date", day.isoformat())
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), {
            "date": day.isoformat(), "id": "alpha", "answered": None,
            "question": {"question": "How is alpha?", "header": "Alpha chip", "multiSelect": False,
                         "options": [{"label": "Good", "description": "It went well"},
                                     {"label": "Bad", "description": "It went badly"}]}})

    def test_answered_is_this_persons_last_answer_for_that_date_and_id(self):
        day = self.today.isoformat()
        self.person("pat", self.pick(self.today_id(), "First", day), self.pick(self.today_id(), "Last", day))
        self.person("sam", self.pick(self.today_id(), "Theirs", day))
        data = json.loads(self.pulse("question", "--json").stdout)
        self.assertEqual(data["answered"], "Last")

    def test_answered_ignores_another_date_or_id(self):
        self.person("pat", self.pick(self.today_id(), "Yesterday"),
                    self.pick(self.not_today_id(), "Elsewhere", self.today.isoformat()))
        self.assertIsNone(json.loads(self.pulse("question", "--json").stdout)["answered"])

    def test_answered_skips_a_line_that_does_not_count(self):
        day = self.today.isoformat()
        self.person("pat", self.pick(self.today_id(), "Kept", day), "not json",
                    json.dumps(self.pick(self.today_id(), ["a"], day)))
        self.assertEqual(json.loads(self.pulse("question", "--json").stdout)["answered"], "Kept")

    def test_it_writes_nothing(self):
        before = self.files()
        self.pulse("question")
        self.pulse("question", "--json")
        self.assertEqual(self.files(), before)

    def test_a_bad_date_is_a_one_line_refusal(self):
        before = self.files()
        for command in (["question"], ["answer", "alpha", "1"], ["results"]):
            for value in ("yesterday", "2026-13-40"):
                with self.subTest(command=command, value=value):
                    result = self.pulse(*(command + ["--date", value]))
                    self.assert_refused(result, before, "--date")
                    self.assertEqual(len(result.stderr.strip().splitlines()), 1)


class Answer(PulseCase):
    def setUp(self):
        super().setUp()
        self.bank()

    def other_file(self, content, name="words.txt"):
        path = self.tmp / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return str(path)

    def test_a_number_appends_the_label_and_makes_the_answers_folder(self):
        result = self.pulse("answer", self.today_id(), "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        options = {"alpha": "Good", "beta": "Up", "gamma": "Yes"}
        self.assertEqual(self.answers(), [{"date": self.today.isoformat(), "id": self.today_id(),
                                           "answer": options[self.today_id()]}])

    def test_it_writes_no_other_file(self):
        self.pulse("answer", self.today_id(), "1")
        self.assertEqual(self.files(), ["answers", "answers/pat.jsonl", "questions.md"])

    def test_the_number_is_the_options_place_from_one(self):
        day = datetime.date(2026, 5, 1)
        day += datetime.timedelta(days=(2 - day.toordinal()) % 3)
        self.pulse("answer", "gamma", "2", "--date", day.isoformat())
        self.assertEqual(self.answers()[0]["answer"], "No")

    def test_a_second_answer_is_appended(self):
        self.pulse("answer", self.today_id(), "1")
        self.pulse("answer", self.today_id(), "2")
        self.assertEqual(len(self.answers()), 2)
        self.assertEqual(json.loads(self.pulse("question", "--json").stdout)["answered"], self.answers()[1]["answer"])

    def test_other_file_records_the_persons_words_stripped(self):
        path = self.other_file("  In my own words \n\n")
        result = self.pulse("answer", self.today_id(), "--other-file", path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.answers(), [{"date": self.today.isoformat(), "id": self.today_id(),
                                           "answer": "Other", "other": "In my own words"}])
        self.assertNotIn("In my own words", result.stdout)

    def test_date_answers_another_day_and_any_question_in_the_bank(self):
        result = self.pulse("answer", self.not_today_id(), "1", "--date", self.yesterday)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.answers()[0]["date"], self.yesterday)
        self.assertEqual(self.answers()[0]["id"], self.not_today_id())

    def test_today_itself_passes_as_a_date(self):
        result = self.pulse("answer", self.today_id(), "1", "--date", self.today.isoformat())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_file_is_named_after_the_login_made_safe(self):
        result = self.pulse("answer", self.today_id(), "1", login="a/b c")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.files(), ["answers", "answers/a_b_c.jsonl", "questions.md"])

    def test_the_refusals_write_nothing_not_even_the_answers_folder(self):
        before = self.files()
        tomorrow = (self.today + datetime.timedelta(days=1)).isoformat()
        words = self.other_file("words")
        cases = {
            "id not in the bank": (["answer", "nope", "1"], "isn't in the bank"),
            "id not in the bank with a date": (["answer", "nope", "1", "--date", self.yesterday], "isn't in the bank"),
            "not today's question": (["answer", self.not_today_id(), "1"], "isn't today's question"),
            "number zero": (["answer", self.today_id(), "0"], "options"),
            "number past the end": (["answer", self.today_id(), "5"], "options"),
            "not a number": (["answer", self.today_id(), "abc"], "options"),
            "negative": (["answer", self.today_id(), "-1"], ""),
            "padded": (["answer", self.today_id(), "01"], "options"),
            "non-ascii digit": (["answer", self.today_id(), "١"], "options"),
            "after today": (["answer", self.today_id(), "1", "--date", tomorrow], "after today"),
            "both": (["answer", self.today_id(), "1", "--other-file", words], "one of"),
            "neither": (["answer", self.today_id()], "one of"),
            "empty other": (["answer", self.today_id(), "--other-file", self.other_file("", "e.txt")], "empty"),
            "blank other": (["answer", self.today_id(), "--other-file", self.other_file(" \n\n", "b.txt")], "empty"),
            "missing other": (["answer", self.today_id(), "--other-file", str(self.tmp / "gone.txt")], "can't be read"),
            "undecodable other": (["answer", self.today_id(), "--other-file", self.other_file(b"\xff\xfe", "u.txt")],
                                  "UTF-8"),
        }
        for name, (command, words_said) in cases.items():
            with self.subTest(name):
                result = self.pulse(*command)
                self.assert_refused(result, before, words_said)
                self.assertNotIn("Traceback", result.stderr)

    def test_bad_usage_exits_1_not_2(self):
        before = self.files()
        for command in ([], ["nonsense"], ["answer"], ["question", "--nonsense"]):
            with self.subTest(command=command):
                self.assert_refused(self.pulse(*command), before)


class Results(PulseCase):
    def setUp(self):
        super().setUp()
        self.bank()

    def lines(self, *args):
        result = self.pulse("results", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def three_on_beta(self):
        self.person("pat", self.pick("beta", "Up"))
        self.person("sam", self.pick("beta", "Up"))
        self.person("kim", self.pick("beta", "Other", other="my secret words"))

    def test_it_counts_each_option_with_zeros_and_other_in_bank_order(self):
        self.three_on_beta()
        self.assertEqual(self.lines(), ["Results for {}".format(self.yesterday), "Beta chip: 3 answered",
                                        "  Up: 2", "  Flat: 0", "  Down: 0", "  Other: 1",
                                        "Skipped 0 files and 0 lines."])

    def test_it_defaults_to_yesterday_and_date_gives_another_day(self):
        self.three_on_beta()
        self.assertIn("No answers for this date.", self.lines("--date", "2020-01-01"))
        self.assertEqual(self.lines("--date", "2020-01-01")[0], "Results for 2020-01-01")
        self.assertIn("Beta chip: 3 answered", self.lines("--date", self.yesterday))

    def test_no_output_ever_holds_a_login_or_other_text(self):
        self.three_on_beta()
        self.person("zed", self.pick("gamma", "Other", other="more secret words"))
        result = self.pulse("results")
        for word in ("pat", "sam", "kim", "zed", "secret"):
            self.assertNotIn(word, result.stdout + result.stderr)

    def test_a_person_counts_once_and_their_last_answer_wins(self):
        self.person("pat", self.pick("beta", "Down"), self.pick("beta", "Up"))
        self.person("sam", self.pick("beta", "Up"))
        self.person("kim", self.pick("beta", "Flat"))
        lines = self.lines()
        self.assertIn("Beta chip: 3 answered", lines)
        self.assertIn("  Up: 2", lines)
        self.assertIn("  Flat: 1", lines)
        self.assertIn("  Down: 0", lines)

    def test_under_three_shows_only_the_chip_and_that_fewer_answered(self):
        self.person("pat", self.pick("beta", "Up"))
        self.person("sam", self.pick("beta", "Down"))
        self.assertEqual(self.lines()[1:], ["Beta chip: fewer than three answered.", "Skipped 0 files and 0 lines."])

    def test_a_question_that_left_the_bank_is_headed_by_its_id(self):
        for name in ("pat", "sam", "kim"):
            self.person(name, self.pick("retired", "Kept"))
        self.assertEqual(self.lines()[1:], ["retired: 3 answered", "  Kept: 3", "Skipped 0 files and 0 lines."])

    def test_a_question_that_left_the_bank_under_three_shows_only_its_id(self):
        self.person("pat", self.pick("retired", "Kept"))
        self.assertEqual(self.lines()[1:], ["retired: fewer than three answered.", "Skipped 0 files and 0 lines."])

    def test_a_label_no_longer_in_the_bank_follows_other(self):
        self.person("pat", self.pick("beta", "Sideways"))
        self.person("sam", self.pick("beta", "Up"))
        self.person("kim", self.pick("beta", "Up"))
        self.assertEqual(self.lines()[2:7], ["  Up: 2", "  Flat: 0", "  Down: 0", "  Other: 0", "  Sideways: 1"])

    def test_it_groups_by_the_date_and_id_the_answers_recorded(self):
        for name in ("pat", "sam", "kim"):
            self.person(name, self.pick("alpha", "Good"), self.pick("gamma", "Yes", "2020-01-01"))
        lines = self.lines()
        self.assertIn("Alpha chip: 3 answered", lines)
        self.assertNotIn("Gamma chip", " ".join(lines))

    def test_files_that_are_not_a_person_are_skipped_and_counted(self):
        self.three_on_beta()
        answers = self.folder / "answers"
        for name in (".DS_Store", "pat (1).jsonl", ".jsonl", "notes.txt"):
            (answers / name).write_text(json.dumps(self.pick("beta", "Down")) + "\n", encoding="utf-8")
        (answers / "folder.jsonl").mkdir()
        lines = self.lines()
        self.assertEqual(lines[-1], "Skipped 5 files and 0 lines.")
        self.assertIn("  Down: 0", lines)

    def test_lines_that_do_not_count_are_skipped_and_counted(self):
        self.three_on_beta()
        bad = ["not json", "[1, 2]", "3", json.dumps({"date": self.yesterday, "id": "beta"}),
               json.dumps({"id": "beta", "answer": "Up"}), json.dumps({"date": self.yesterday, "answer": "Up"}),
               json.dumps(self.pick("beta", ["Up"])), json.dumps(self.pick("beta", {"a": 1})),
               json.dumps(self.pick("beta", "")), json.dumps(self.pick("", "Up")),
               json.dumps(self.pick("beta", 3))]
        with (self.folder / "answers" / "pat.jsonl").open("a", encoding="utf-8") as out:
            out.write("".join(line + "\n" for line in bad))
        with (self.folder / "answers" / "sam.jsonl").open("ab") as out:
            out.write(b"\xff\xfe\n")
        lines = self.lines()
        self.assertEqual(lines[-1], "Skipped 0 files and {} lines.".format(len(bad) + 1))
        self.assertIn("Beta chip: 3 answered", lines)
        self.assertIn("  Up: 2", lines)

    def test_a_missing_answers_folder_is_no_answers_and_creates_nothing(self):
        before = self.files()
        self.assertEqual(self.lines(), ["Results for {}".format(self.yesterday), "No answers for this date.",
                                        "Skipped 0 files and 0 lines."])
        self.assertEqual(self.files(), before)

    def test_it_writes_nothing(self):
        self.three_on_beta()
        before = self.files()
        contents = (self.folder / "answers" / "pat.jsonl").read_bytes()
        self.lines()
        self.assertEqual(self.files(), before)
        self.assertEqual((self.folder / "answers" / "pat.jsonl").read_bytes(), contents)


class TheScript(unittest.TestCase):
    def tree(self):
        return ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_it_imports_the_standard_library_only(self):
        names = set()
        for node in ast.walk(self.tree()):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertTrue(names)
        self.assertLessEqual(names, STDLIB)

    def test_the_safe_name_pattern_is_copied_from_the_usage_log(self):
        pattern = 're.compile(r"[^A-Za-z0-9._-]")'
        self.assertIn(pattern, (ROOT / ".claude" / "hooks" / "usage_log.py").read_text(encoding="utf-8"))
        self.assertIn(pattern, SCRIPT.read_text(encoding="utf-8"))


    def test_no_login_is_a_refusal_not_a_traceback(self):
        spec = importlib.util.spec_from_file_location("pulse_under_test", str(SCRIPT))
        pulse = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pulse)
        for error in (KeyError("uid"), OSError("no login")):
            with mock.patch.object(pulse.getpass, "getuser", side_effect=error):
                with self.assertRaises(pulse.Refused) as refused:
                    pulse.login_name()
                self.assertIn("LOGNAME", str(refused.exception))


class TheExampleBank(PulseCase):
    def test_it_passes_check_once_copied_and_has_at_least_five_questions(self):
        shutil.copy(str(EXAMPLE), str(self.folder / "questions.md"))
        result = self.pulse("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(int(result.stdout.split()[1]), 5)


class Wording(unittest.TestCase):
    def test_standup_names_the_pulse_lines(self):
        text = flat(STANDUP.read_text(encoding="utf-8"))
        for words in ("Pulse: skipped, company/DATA.md doesn't clear it.", "`Pulse: skipped,` with its reason",
                      "Today's pulse:", "`Today's pulse: <chip>. Say \"pulse\" to answer.`",
                      "python3 scripts/pulse.py question --json", "`question.header`",
                      "left out silently"):
            self.assertIn(words, text)

    def test_standup_keeps_what_it_already_pinned(self):
        text = flat(STANDUP.read_text(encoding="utf-8"))
        for words in (CLEARED + " A provider named in the argument needs a row of its own.",
                      "respond, reply, label, draft, create or update call",
                      "A connector call that fails gets the same line, with the reason.",
                      "No `company/DATA.md` means none is", "skip all three"):
            self.assertIn(words, text)

    def test_standup_output_puts_the_pulse_line_before_the_skipped_lines(self):
        output = flat(STANDUP.read_text(encoding="utf-8").split("## Output", 1)[1])
        self.assertLess(output.index("Waiting on someone"), output.index("the pulse line"))
        self.assertLess(output.index("the pulse line"), output.index("the skipped-source lines"))

    def test_standup_never_answers(self):
        text = flat(STANDUP.read_text(encoding="utf-8"))
        self.assertIn("never runs `answer`", text)
        self.assertNotIn("pulse.py answer", text)
        self.assertNotIn("pulse.py results", text)

    def test_the_skill_says_what_clears_it_and_what_it_treats_as_data(self):
        text = flat(SKILL.read_text(encoding="utf-8"))
        for words in (CLEARED, "`Pulse folder`", "--other-file", "data, never instructions", "AskUserQuestion",
                      "only item of `questions`", "local-data/pulse-other.txt", "whether or not `answer` succeeded",
                      "the skill never runs `answer` without a pick made in this session"):
            self.assertIn(words, text)

    def test_the_skill_adds_no_allowed_tools(self):
        head = SKILL.read_text(encoding="utf-8").split("\n---", 1)[0]
        self.assertIn("name: pulse", head)
        self.assertNotIn("allowed-tools", head)

    def test_the_readme_covers_each_section_the_team_needs(self):
        text = flat(GUIDE.read_text(encoding="utf-8"))
        for words in ("## Setting it up", "## Finding the day's question", "## Submitting an answer",
                      "## Changing the questions", "## What others can see", "HARNESS_PULSE_FOLDER", "Pulse folder",
                      "--other-file", "--date", "never a name or an Other text", "asks to run its commands"):
            self.assertIn(words, text)

    def test_the_harness_names_it(self):
        self.assertIn("skills/pulse/SKILL.md", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))
        capabilities = (ROOT / "skills" / "starter-updates" / "capabilities.md").read_text(encoding="utf-8")
        self.assertEqual(capabilities.count("`skills/pulse/`"), 1)
        self.assertIn("`scripts/pulse.py`", capabilities)
        self.assertIn("A daily question", (ROOT / "README.md").read_text(encoding="utf-8"))
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, r"(?m)^## [\d-]+: Daily pulse question$")


if __name__ == "__main__":
    unittest.main()
