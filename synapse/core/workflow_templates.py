"""Predefined workflow templates."""
from .workflow import Workflow, WorkflowNode


def get_code_review_workflow():
    w = Workflow("Code Review")
    w.nodes = [
        WorkflowNode("Read File", "", "Read the file at path {{input_path}} and return its contents."),
        WorkflowNode("Analyze", "", "Analyze this code for bugs, style issues, and improvements:\n\n{{Read File}}"),
        WorkflowNode("Write Review", "", "Write a concise code review with specific suggestions:\n\n{{Analyze}}"),
    ]
    return w


def get_research_workflow():
    w = Workflow("Research")
    w.nodes = [
        WorkflowNode("Web Search", "", "Search the web for: {{input_query}}. Return top 3 relevant URLs and snippets."),
        WorkflowNode("Scrape Top 3", "", "Scrape and summarize content from these URLs:\n\n{{Web Search}}"),
        WorkflowNode("Summarize", "", "Summarize the research findings:\n\n{{Scrape Top 3}}"),
    ]
    return w


def get_test_fix_workflow():
    w = Workflow("Test & Fix")
    w.nodes = [
        WorkflowNode("Run Tests", "", "Run the test suite (pytest or npm test) and report results."),
        WorkflowNode("Analyze Failures", "", "If tests failed, analyze the output and suggest fixes:\n\n{{Run Tests}}"),
        WorkflowNode("Apply Fix", "", "Apply the suggested fixes and re-run tests."),
    ]
    return w


TEMPLATES = {
    "code_review": get_code_review_workflow,
    "research": get_research_workflow,
    "test_fix": get_test_fix_workflow,
}


def get_template(name):
    fn = TEMPLATES.get(name)
    return fn() if fn else None
