from __future__ import annotations

from copy import deepcopy
from textwrap import dedent
from typing import Any, Dict, List


def _strip(text: str) -> str:
    return dedent(text).strip()


BASE_QUESTIONS_TEMPLATE: List[Dict[str, Any]] = [
    {
        "title": "Mirror the {topic} Message",
        "question_text": _strip(
            """
            You collected feedback about {topic} and want to display it in reverse order.
            Input:
            - A single line of text.
            Output:
            - The characters of the line in reverse order.
            Example:
            Input
            loops and lists
            Output
            stsil dna spool
            """
        ),
        "difficulty_level": "Bronze",
        "starter_code": _strip(
            """
            def main():
                message = input().rstrip("\n")
                # TODO: print the message in reverse order
                print(message)

            if __name__ == "__main__":
                main()
            """
        ),
        "reference_solution": _strip(
            """
            def main():
                message = input().rstrip("\n")
                print(message[::-1])

            if __name__ == "__main__":
                main()
            """
        ),
        "tests": [
            {"input": "Loops and lists\n", "expected": "stsil dna spooL\n", "visibility": "public"},
            {"input": "topic\n", "expected": "cipot\n", "visibility": "public"},
            {"input": "\n", "expected": "\n", "visibility": "private"},
        ],
    },
    {
        "title": "Total {topic} Minutes",
        "question_text": _strip(
            """
            Each study session for {topic} is logged as minutes. Compute the total minutes for the day.
            Input:
            - Line 1: integer n (1 <= n <= 100).
            - Line 2: n space-separated integers representing minutes.
            Output:
            - The sum of all minutes.
            Example:
            Input
            4
            10 20 15 5
            Output
            50
            """
        ),
        "difficulty_level": "Bronze",
        "starter_code": _strip(
            """
            def main():
                count = int(input().strip())
                values = list(map(int, input().split()))
                # TODO: print the total study minutes
                print(0)

            if __name__ == "__main__":
                main()
            """
        ),
        "reference_solution": _strip(
            """
            def main():
                count = int(input().strip())
                values = list(map(int, input().split()))
                if len(values) != count:
                    values = values[:count]
                print(sum(values))

            if __name__ == "__main__":
                main()
            """
        ),
        "tests": [
            {"input": "4\n10 20 15 5\n", "expected": "50\n", "visibility": "public"},
            {"input": "3\n5 5 5\n", "expected": "15\n", "visibility": "public"},
            {"input": "5\n1 2 3 4 5\n", "expected": "15\n", "visibility": "private"},
        ],
    },
    {
        "title": "Average {topic} Accuracy",
        "question_text": _strip(
            """
            Compute the average quiz accuracy for {topic}. Report the result rounded to one decimal place.
            Input:
            - Line 1: integer n (1 <= n <= 50).
            - Line 2: n space-separated integers representing percentages.
            Output:
            - The average as a single line with one decimal place.
            Example:
            Input
            3
            70 80 90
            Output
            80.0
            """
        ),
        "difficulty_level": "Silver",
        "starter_code": _strip(
            """
            def main():
                count = int(input().strip())
                scores = list(map(int, input().split()))
                # TODO: print the average as one decimal place
                print(0.0)

            if __name__ == "__main__":
                main()
            """
        ),
        "reference_solution": _strip(
            """
            def main():
                count = int(input().strip())
                scores = list(map(int, input().split()))
                if len(scores) != count:
                    scores = scores[:count]
                average = sum(scores) / count if count else 0.0
                print(f"{average:.1f}")

            if __name__ == "__main__":
                main()
            """
        ),
        "tests": [
            {"input": "3\n70 80 90\n", "expected": "80.0\n", "visibility": "public"},
            {"input": "4\n100 100 80 60\n", "expected": "85.0\n", "visibility": "public"},
            {"input": "2\n45 55\n", "expected": "50.0\n", "visibility": "private"},
        ],
    },
    {
        "title": "Longest {topic} Practice Streak",
        "question_text": _strip(
            """
            A streak log stores 1 for a successful day of {topic} practice and 0 otherwise.
            Input:
            - Line 1: integer n (1 <= n <= 200).
            - Line 2: n space-separated values 0 or 1.
            Output:
            - The length of the longest consecutive run of 1s.
            Example:
            Input
            7
            1 1 0 1 1 1 0
            Output
            3
            """
        ),
        "difficulty_level": "Silver",
        "starter_code": _strip(
            """
            def main():
                count = int(input().strip())
                bits = list(map(int, input().split()))
                # TODO: compute the longest consecutive streak of 1s
                print(0)

            if __name__ == "__main__":
                main()
            """
        ),
        "reference_solution": _strip(
            """
            def main():
                count = int(input().strip())
                bits = list(map(int, input().split()))
                if len(bits) != count:
                    bits = bits[:count]
                best = current = 0
                for bit in bits:
                    if bit == 1:
                        current += 1
                        best = max(best, current)
                    else:
                        current = 0
                print(best)

            if __name__ == "__main__":
                main()
            """
        ),
        "tests": [
            {"input": "7\n1 1 0 1 1 1 0\n", "expected": "3\n", "visibility": "public"},
            {"input": "5\n0 0 0 0 0\n", "expected": "0\n", "visibility": "public"},
            {"input": "6\n1 1 1 1 1 1\n", "expected": "6\n", "visibility": "private"},
        ],
    },
    {
        "title": "Weekly {topic} Sprint Summary",
        "question_text": _strip(
            """
            Summarise weekly activity for {topic}. Each record contains the week label, minutes spent, and completed tasks.
            Input:
            - Line 1: integer w (1 <= w <= 12).
            - Next w lines: label minutes completed
            Output:
            - Line 1: 'Total minutes: X'.
            - Line 2: 'Top week: LABEL' where LABEL has the highest completed value (ties broken by earliest occurrence).
            Example:
            Input
            3
            Week1 180 4
            Week2 200 5
            Week3 160 6
            Output
            Total minutes: 540
            Top week: Week3
            """
        ),
        "difficulty_level": "Gold",
        "starter_code": _strip(
            """
            def main():
                weeks = int(input().strip())
                records = []
                for _ in range(weeks):
                    parts = input().split()
                    records.append(parts)
                # TODO: compute totals and determine the top week
                print('Total minutes: 0')
                print('Top week: TBD')

            if __name__ == "__main__":
                main()
            """
        ),
        "reference_solution": _strip(
            """
            def main():
                weeks = int(input().strip())
                records = []
                for _ in range(weeks):
                    label, minutes, completed = input().split()
                    records.append((label, int(minutes), int(completed)))
                total_minutes = sum(r[1] for r in records)
                best_label = records[0][0] if records else 'N/A'
                best_completed = records[0][2] if records else -1
                for label, minutes, completed in records:
                    if completed > best_completed:
                        best_completed = completed
                        best_label = label
                print(f'Total minutes: {total_minutes}')
                print(f'Top week: {best_label}')

            if __name__ == "__main__":
                main()
            """
        ),
        "tests": [
            {"input": "3\nWeek1 180 4\nWeek2 200 5\nWeek3 160 6\n", "expected": "Total minutes: 540\nTop week: Week3\n", "visibility": "public"},
            {"input": "2\nSprintA 120 3\nSprintB 90 5\n", "expected": "Total minutes: 210\nTop week: SprintB\n", "visibility": "public"},
            {"input": "1\nOnly 75 2\n", "expected": "Total minutes: 75\nTop week: Only\n", "visibility": "private"},
        ],
    },
]

BASE_PACKS: List[Dict[str, Any]] = [
    {
        "challenge_set_title": "Week {week} {topic} Fundamentals",
        "questions": deepcopy(BASE_QUESTIONS_TEMPLATE),
    },
    {
        "challenge_set_title": "Week {week} {topic} Practice Pack",
        "questions": deepcopy(
            [
                BASE_QUESTIONS_TEMPLATE[1],
                BASE_QUESTIONS_TEMPLATE[0],
                BASE_QUESTIONS_TEMPLATE[3],
                BASE_QUESTIONS_TEMPLATE[2],
                BASE_QUESTIONS_TEMPLATE[4],
            ]
        ),
    },
]

RUBY_PACKS: List[Dict[str, Any]] = [
    {
        "challenge_set_title": "Week {week} {topic} Ruby Analysis",
        "questions": [
            deepcopy(
                {
                    "title": "{topic} Assessment Dashboard",
                    "question_text": _strip(
                        """
                        Design a reporting tool for {topic} assessments.
                        Input:
                        - Line 1: integer n (1 <= n <= 100).
                        - Next n lines: student score time where score is an integer and time is minutes spent.
                        Output:
                        - Line 1: 'Average score: X.X' rounded to one decimal.
                        - Line 2: 'Top performer: NAME' for the highest score (ties broken by lowest time, then alphabetical).
                        - Line 3: 'Median score: Y.Y' rounded to one decimal.
                        """
                    ),
                    "difficulty_level": "Ruby",
                    "starter_code": _strip(
                        """
                        def parse_record(line: str) -> tuple[str, int, int]:
                            name, score, minutes = line.split()
                            return name, int(score), int(minutes)

                        def main():
                            count = int(input().strip())
                            records = [parse_record(input()) for _ in range(count)]
                            print('Average score: 0.0')
                            print('Top performer: TBD')
                            print('Median score: 0.0')

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "reference_solution": _strip(
                        """
                        def parse_record(line: str) -> tuple[str, int, int]:
                            name, score, minutes = line.split()
                            return name, int(score), int(minutes)

                        def median(values: list[int]) -> float:
                            values = sorted(values)
                            mid = len(values) // 2
                            if len(values) % 2 == 1:
                                return float(values[mid])
                            return (values[mid - 1] + values[mid]) / 2.0

                        def main():
                            count = int(input().strip())
                            records = [parse_record(input()) for _ in range(count)]
                            if not records:
                                print('Average score: 0.0')
                                print('Top performer: N/A')
                                print('Median score: 0.0')
                                return
                            total = sum(score for _, score, _ in records)
                            average = total / len(records)
                            top = min(records, key=lambda r: (-r[1], r[2], r[0]))
                            scores = [score for _, score, _ in records]
                            med = median(scores)
                            print(f'Average score: {average:.1f}')
                            print(f'Top performer: {top[0]}')
                            print(f'Median score: {med:.1f}')

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "tests": [
                        {"input": "3\nAva 78 42\nBen 91 30\nCara 91 28\n", "expected": "Average score: 86.7\nTop performer: Cara\nMedian score: 91.0\n", "visibility": "public"},
                        {"input": "2\nDev 65 50\nElle 70 65\n", "expected": "Average score: 67.5\nTop performer: Elle\nMedian score: 67.5\n", "visibility": "public"},
                        {"input": "4\nJo 60 40\nKa 80 60\nLi 80 45\nMo 90 70\n", "expected": "Average score: 77.5\nTop performer: Li\nMedian score: 80.0\n", "visibility": "private"},
                    ],
                }
            )
        ],
    },
]

EMERALD_PACKS: List[Dict[str, Any]] = [
    {
        "challenge_set_title": "Week {week} {topic} Emerald Tracker",
        "questions": [
            deepcopy(
                {
                    "title": "{topic} Project Analytics",
                    "question_text": _strip(
                        """
                        Plan a cohort project tracker for {topic}.
                        Input:
                        - Line 1: integer m (1 <= m <= 50).
                        - Next m lines: team completed backlog where completed and backlog are integers.
                        - Last line: integer target representing required completed tasks.
                        Output:
                        - Line 1: 'Total completed: X'.
                        - Line 2: 'Teams meeting target: COUNT'.
                        - Line 3: 'Backlog clearance (%): Y.Y' averaged across teams.
                        - Line 4: team names ordered by descending clearance percentage (ties alphabetical).
                        """
                    ),
                    "difficulty_level": "Emerald",
                    "starter_code": _strip(
                        """
                        def parse_team(line: str) -> tuple[str, int, int]:
                            name, completed, backlog = line.split()
                            return name, int(completed), int(backlog)

                        def main():
                            teams = int(input().strip())
                            records = [parse_team(input()) for _ in range(teams)]
                            target = int(input().strip())
                            print('Total completed: 0')
                            print('Teams meeting target: 0')
                            print('Backlog clearance (%): 0.0')
                            print('Ranking:')

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "reference_solution": _strip(
                        """
                        def parse_team(line: str) -> tuple[str, int, int]:
                            name, completed, backlog = line.split()
                            return name, int(completed), int(backlog)

                        def clearance_percent(completed: int, backlog: int) -> float:
                            total = completed + backlog
                            if total == 0:
                                return 100.0
                            return (completed / total) * 100.0

                        def main():
                            teams = int(input().strip())
                            records = [parse_team(input()) for _ in range(teams)]
                            target = int(input().strip())
                            total_completed = sum(r[1] for r in records)
                            meeting = sum(1 for r in records if r[1] >= target)
                            averages = [clearance_percent(c, b) for _, c, b in records]
                            average_clearance = sum(averages) / len(averages) if averages else 0.0
                            ranking = sorted(records, key=lambda r: (-clearance_percent(r[1], r[2]), r[0]))
                            names = ','.join(name for name, _, _ in ranking)
                            print(f'Total completed: {total_completed}')
                            print(f'Teams meeting target: {meeting}')
                            print(f'Backlog clearance (%): {average_clearance:.1f}')
                            print(f'Ranking: {names}')

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "tests": [
                        {"input": "3\nAlpha 12 3\nBravo 9 6\nCharlie 15 5\n10\n", "expected": "Total completed: 36\nTeams meeting target: 2\nBacklog clearance (%): 63.7\nRanking: Alpha,Charlie,Bravo\n", "visibility": "public"},
                        {"input": "2\nTeamA 5 5\nTeamB 5 0\n4\n", "expected": "Total completed: 10\nTeams meeting target: 2\nBacklog clearance (%): 75.0\nRanking: TeamB,TeamA\n", "visibility": "public"},
                        {"input": "1\nSolo 0 0\n1\n", "expected": "Total completed: 0\nTeams meeting target: 0\nBacklog clearance (%): 100.0\nRanking: Solo\n", "visibility": "private"},
                    ],
                }
            )
        ],
    },
]

DIAMOND_PACKS: List[Dict[str, Any]] = [
    {
        "challenge_set_title": "Week {week} {topic} Diamond Dashboard",
        "questions": [
            deepcopy(
                {
                    "title": "{topic} Cohort Console",
                    "question_text": _strip(
                        """
                        Create a comprehensive semester dashboard for {topic}.
                        Input:
                        - Line 1: integer q (1 <= q <= 100) representing number of queries.
                        - Each of the next q lines is either:
                          ADD cohort score minutes (adds a record) or
                          REPORT cohort (requests the average score and total minutes for that cohort).
                        Output:
                        - For each REPORT command, print 'cohort average-score total-minutes' with average rounded to one decimal.
                        Example:
                        Input
                        5
                        ADD A 80 120
                        ADD B 75 90
                        ADD A 90 150
                        REPORT A
                        REPORT B
                        Output
                        A 85.0 270
                        B 75.0 90
                        """
                    ),
                    "difficulty_level": "Diamond",
                    "starter_code": _strip(
                        """
                        def main():
                            queries = int(input().strip())
                            data: dict[str, list[tuple[int, int]]] = {}
                            for _ in range(queries):
                                parts = input().split()
                                # TODO: process ADD and REPORT commands
                                pass

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "reference_solution": _strip(
                        """
                        def main():
                            queries = int(input().strip())
                            data: dict[str, list[tuple[int, int]]] = {}
                            for _ in range(queries):
                                parts = input().split()
                                action = parts[0]
                                if action == 'ADD':
                                    cohort, score, minutes = parts[1], int(parts[2]), int(parts[3])
                                    data.setdefault(cohort, []).append((score, minutes))
                                elif action == 'REPORT':
                                    cohort = parts[1]
                                    records = data.get(cohort, [])
                                    if not records:
                                        print(f"{cohort} 0.0 0")
                                        continue
                                    total_score = sum(score for score, _ in records)
                                    total_minutes = sum(minutes for _, minutes in records)
                                    average = total_score / len(records)
                                    print(f"{cohort} {average:.1f} {total_minutes}")
                                else:
                                    raise ValueError('Unknown command')

                        if __name__ == "__main__":
                            main()
                        """
                    ),
                    "tests": [
                        {"input": "5\nADD A 80 120\nADD B 75 90\nADD A 90 150\nREPORT A\nREPORT B\n", "expected": "A 85.0 270\nB 75.0 90\n", "visibility": "public"},
                        {"input": "4\nADD X 100 60\nREPORT X\nREPORT Y\nREPORT X\n", "expected": "X 100.0 60\nY 0.0 0\nX 100.0 60\n", "visibility": "public"},
                        {"input": "6\nADD Z 50 40\nADD Z 70 55\nADD M 90 100\nREPORT Z\nREPORT M\nREPORT Z\n", "expected": "Z 60.0 95\nM 90.0 100\nZ 60.0 95\n", "visibility": "private"},
                    ],
                }
            )
        ],
    },
]


def _format_pack(raw: Dict[str, Any], week: int, topic: str) -> Dict[str, Any]:
    pack = deepcopy(raw)
    pack["challenge_set_title"] = pack["challenge_set_title"].format(week=week, topic=topic)
    for question in pack["questions"]:
        question["title"] = question["title"].format(topic=topic)
        question["question_text"] = question["question_text"].format(topic=topic)
    return pack


def get_fallback_payload(kind: str, week: int, topic_title: str) -> Dict[str, Any]:
    key = "base" if kind in {"base", "common"} else kind
    if key == "base":
        source = BASE_PACKS
    elif key == "ruby":
        source = RUBY_PACKS
    elif key == "emerald":
        source = EMERALD_PACKS
    else:
        source = DIAMOND_PACKS
    index = (week - 1) % len(source)
    return _format_pack(source[index], week, topic_title)


__all__ = ["get_fallback_payload"]
