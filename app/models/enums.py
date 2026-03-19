"""Enum definitions for assignments, submissions, and evaluations."""

import enum


class AssignmentType(str, enum.Enum):
    """Assignment type enumeration."""

    PRACTICAL = "practical"      # practical assignment
    INQUIRY = "inquiry"          # inquiry assignment
    PROJECT = "project"          # project-based assignment


class PracticalSubType(str, enum.Enum):
    """Practical assignment subtypes."""

    VISIT = "visit"              # visit / field study
    SIMULATION = "simulation"    # simulation / role play
    OBSERVATION = "observation"  # observation / experience


class InquirySubType(str, enum.Enum):
    """Inquiry assignment subtypes."""

    LITERATURE = "literature"    # literature inquiry
    SURVEY = "survey"            # survey inquiry
    EXPERIMENT = "experiment"    # experiment inquiry


class InquiryDepth(str, enum.Enum):
    """Inquiry depth levels."""

    BASIC = "basic"              # basic inquiry
    INTERMEDIATE = "intermediate" # intermediate inquiry
    DEEP = "deep"                # deep inquiry


class SubmissionMode(str, enum.Enum):
    """Submission modes."""

    PHASED = "phased"            # phased submissions
    ONCE = "once"                # single submission
    MIXED = "mixed"              # mixed submission


class SubmissionStatus(str, enum.Enum):
    """Submission status."""

    DRAFT = "draft"              # draft
    SUBMITTED = "submitted"      # submitted
    GRADED = "graded"            # graded


class EvaluationType(str, enum.Enum):
    """Evaluation type."""

    TEACHER = "teacher"          # teacher evaluation
    SELF = "self"                # self evaluation
    PEER = "peer"                # peer evaluation


class EvaluationLevel(str, enum.Enum):
    """Evaluation level (4-tier)."""

    EXCELLENT = "excellent"  # excellent
    GOOD = "good"            # good
    PASS = "pass"            # pass
    IMPROVE = "improve"      # needs improvement


class SchoolStage(str, enum.Enum):
    """School stage."""

    PRIMARY = "primary"          # primary school
    MIDDLE = "middle"            # middle school
