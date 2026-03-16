import sys
from unittest.mock import MagicMock
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from synapse.core.workflow import Workflow, WorkflowNode, WorkflowExecutor

def test_variable_resolution():
    wf = Workflow("Test Workflow")
    node1 = WorkflowNode("Step 1", "model1", "Hello world")
    node2 = WorkflowNode("Step 2", "model2", "Reversed: {{Step 1}}")
    wf.nodes = [node1, node2]
    
    # Mocking _run_node_sync to return controlled values
    def mock_run_sync(model, prompt):
        if "Reversed" in prompt:
            return prompt.replace("Reversed: ", "")[::-1]
        return prompt
        
    executor = WorkflowExecutor(wf, None)
    executor._run_node_sync = mock_run_sync
    
    # We can't easily run QThread in a simple script without QApp, 
    # but we can test the internal methods.
    
    # Test _resolve_variables
    resolved = executor._resolve_variables("Input: {{last}}", "Prev Output")
    assert resolved == "Input: Prev Output"
    
    executor.context["Step 1"] = "Logic"
    resolved = executor._resolve_variables("Context: {{Step 1}}", "")
    assert resolved == "Context: Logic"
    
    print("Variable resolution tests passed!")

if __name__ == "__main__":
    test_variable_resolution()
