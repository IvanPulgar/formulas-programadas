from enum import Enum


class VariableScope(str, Enum):
    GLOBAL = "global"
    CATEGORY = "category"
    RESULT = "result"


class VariableType(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    RATE = "rate"
    TIME = "time"
    COUNT = "count"


class FormulaType(str, Enum):
    DIRECT = "direct"
    INVERSE = "inverse"
    SYMBOLIC = "symbolic"
    COMPOSITE = "composite"
    VALIDATION = "validation"


class FormulaCategory(str, Enum):
    GENERAL = "generales"
    PICS = "PICS"
    PICM = "PICM"
    PFCS = "PFCS"
    PFCM = "PFCM"


class CalculationStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


class ValidationResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"
