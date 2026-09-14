import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "chatgpt.GenerationIntervalCleanup.Status",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "GenerationIntervalCleanup") return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            this.cleanupStatusWidget = this.addWidget(
                "text",
                "status",
                "Not run yet (1 prompt = 1 count)",
                () => {},
                { multiline: false }
            );
            this.cleanupStatusWidget.disabled = true;
            this.setSize([Math.max(this.size[0], 430), Math.max(this.size[1], 190)]);
            return result;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            const text = Array.isArray(message?.text) ? message.text[0] : message?.text;
            if (text && this.cleanupStatusWidget) {
                this.cleanupStatusWidget.value = text;
                this.setDirtyCanvas(true, true);
            }
        };
    },
});
