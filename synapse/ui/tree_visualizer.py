import json
import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt5.QtCore import QObject as _QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtWebChannel import QWebChannel

from ..core.tree_service import TreeExportService

log = logging.getLogger(__name__)

D3_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #0d1117;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        }
        .node circle {
            fill: #1f2937;
            stroke: #30363d;
            stroke-width: 2px;
            cursor: pointer;
            transition: fill 0.2s;
        }
        .node.user circle {
            fill: #1d2d50;
            stroke: #58a6ff;
        }
        .node.assistant circle {
            fill: #1a271c;
            stroke: #2ea043;
        }
        .node:hover circle {
            fill: #30363d !important;
        }
        .node text {
            font-size: 11px;
            fill: #8b949e;
            pointer-events: none;
            user-select: none;
        }
        .node:hover text {
            fill: #e6edf3;
        }
        .link {
            fill: none;
            stroke: #21262d;
            stroke-width: 1.5px;
        }
    </style>
</head>
<body>
    <div id="tree-container"></div>
    <script>
        let bridge;
        new QWebChannel(qt.webChannelTransport, function (channel) {
            bridge = channel.objects.bridge;
        });

        function updateTree(data) {
            d3.select("svg").remove();
            if (!data || Object.keys(data).length === 0) return;

            const width = window.innerWidth;
            const height = window.innerHeight;

            const svg = d3.select("#tree-container").append("svg")
                .attr("width", width)
                .attr("height", height)
                .call(d3.zoom().on("zoom", (event) => {
                    g.attr("transform", event.transform);
                }))
                .append("g");

            const g = svg.append("g")
                .attr("transform", "translate(40,0)");

            const tree = d3.tree().nodeSize([40, 180]);
            const root = d3.hierarchy(data);
            tree(root);

            const link = g.selectAll(".link")
                .data(root.links())
                .enter().append("path")
                .attr("class", "link")
                .attr("d", d3.linkHorizontal()
                    .x(d => d.y)
                    .y(d => d.x));

            const node = g.selectAll(".node")
                .data(root.descendants())
                .enter().append("g")
                .attr("class", d => "node " + (d.data.role || "user"))
                .attr("transform", d => `translate(${d.y},${d.x})`)
                .on("click", (event, d) => {
                    if (bridge) {
                        bridge.onNodeClicked(d.data.id);
                    }
                });

            node.append("circle")
                .attr("r", 6);

            node.append("text")
                .attr("dy", ".31em")
                .attr("x", d => d.children ? -10 : 10)
                .style("text-anchor", d => d.children ? "end" : "start")
                .text(d => d.data.name);
        }

        window.addEventListener('resize', () => {
            // Optional: Re-render on resize
        });
    </script>
</body>
</html>
"""

class Bridge(_QObject):
    """Bridge between JS and Python."""
    node_clicked = pyqtSignal(str)
    
    @pyqtSlot(str)
    def onNodeClicked(self, node_id):
        self.node_clicked.emit(node_id)

class ConversationTreeSidebar(QWidget):
    """A sidebar to visualize conversation branches using D3.js."""
    branch_requested = pyqtSignal(str) # Renamed for compatibility
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet("background: #161b22; border-bottom: 1px solid #30363d;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(12, 12, 12, 12)
        
        title = QLabel("Conversation Tree")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #e6edf3;")
        h_layout.addWidget(title)
        
        subtitle = QLabel("Explore branches and forks")
        subtitle.setStyleSheet("color: #8b949e; font-size: 11px;")
        h_layout.addWidget(subtitle)
        
        self.layout.addWidget(header)
        
        # Web View
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.NoContextMenu)
        self.web_view.setHtml(D3_TEMPLATE)
        
        # Bridge
        self.bridge = Bridge()
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        self.bridge.node_clicked.connect(self.branch_requested.emit)
        
        self.layout.addWidget(self.web_view)
        
    def set_conversation(self, conversation):
        """Update the tree with conversation data object."""
        data = TreeExportService.get_tree_data(conversation)
        self._update_web_view(data)

    def refresh(self, history, active_id=None):
        """Compatible refresh method for MainWindow."""
        # Wrap history in a dummy conversation object for the service
        dummy_conv = {"history": history}
        data = TreeExportService.get_tree_data(dummy_conv)
        self._update_web_view(data)

    def _update_web_view(self, data):
        json_data = json.dumps(data)
        script = f"updateTree({json_data});"
        self.web_view.page().runJavaScript(script)

    def apply_theme(self, theme):
        """Compatible apply_theme method."""
        pass
