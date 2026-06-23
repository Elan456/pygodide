from dataclasses import dataclass

from packaging.specifiers import SpecifierSet


@dataclass
class PackageInfo:
    name: str
    specifier: SpecifierSet | None = None

    @property
    def normalized_name(self) -> str:
        return self.name.lower().replace("_", "-")

    def __str__(self) -> str:
        if self.specifier:
            return f"{self.name}{self.specifier}"
        else:
            return self.name
