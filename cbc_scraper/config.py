from types import MappingProxyType

YEAR_TASKS = MappingProxyType(
    {
        2018: tuple(f"Task {number}" for number in range(8)),
        2019: tuple(f"Task {number}" for number in (1, 2, 3, 4, 5, "6a", "6b", 7)),
        2020: tuple(f"Task {number}" for number in range(1, 10)),
        2021: tuple(f"Task {number}" for number in range(11)),
        2022: tuple(
            f"Task {number}" for number in (0, "a1", "a2", "b1", "b2", 5, 6, 7, 8, 9)
        ),
        2023: tuple(f"Task {number}" for number in range(10)),
        2024: tuple(f"Task {number}" for number in range(8)),
        2025: tuple(f"Task {number}" for number in range(8)),
    }
)
