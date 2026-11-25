/**
 * SmartAI - Lightweight Markdown and Code Formatter
 * Parses Markdown syntax, code blocks, lists, and provides copy-to-clipboard functionality.
 */

const MarkdownParser = {
    /**
     * Escapes raw HTML characters to prevent XSS.
     */
    escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    /**
     * Parses Markdown string into safe, formatted HTML.
     */
    render(text) {
        if (!text) return "";

        let content = text;
        const codeBlocks = [];

        // 1. Extract and preserve multiline fenced code blocks ```lang ... ```
        content = content.replace(/```([a-zA-Z0-9_\-#+.]*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const index = codeBlocks.length;
            const language = lang.trim() || "code";
            const escapedCode = this.escapeHtml(code.trim());
            
            codeBlocks.push(`
                <div class="code-block-wrapper">
                    <div class="code-block-header">
                        <span class="code-lang-tag">${language}</span>
                        <button class="code-copy-btn" onclick="MarkdownParser.copyCode(this)" title="Copy Code">
                            <i class="fa-regular fa-copy"></i>
                            <span>Copy code</span>
                        </button>
                    </div>
                    <pre><code class="language-${language}">${escapedCode}</code></pre>
                </div>
            `);
            return `__CODE_BLOCK_${index}__`;
        });

        // 2. Escape any remaining inline HTML
        content = this.escapeHtml(content);

        // 3. Inline code `code`
        content = content.replace(/`([^`]+)`/g, '<code>$1</code>');

        // 4. Headers (# h1, ## h2, ### h3)
        content = content.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        content = content.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        content = content.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        // 5. Bold & Italic
        content = content.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');

        // 6. Blockquotes
        content = content.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

        // 7. Unordered Lists
        content = content.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
        content = content.replace(/(<li>.*<\/li>)/gims, (match) => `<ul>${match}</ul>`);

        // Clean up adjacent duplicate ul wrappers
        content = content.replace(/<\/ul>\s*<ul>/g, '');

        // 8. Paragraphs and line breaks
        const paragraphs = content.split(/\n{2,}/);
        content = paragraphs
            .map(p => {
                p = p.trim();
                if (!p) return "";
                if (p.startsWith("__CODE_BLOCK_") || p.startsWith("<h1>") || p.startsWith("<h2>") || 
                    p.startsWith("<h3>") || p.startsWith("<ul>") || p.startsWith("<blockquote>")) {
                    return p;
                }
                return `<p>${p.replace(/\n/g, "<br>")}</p>`;
            })
            .join("\n");

        // 9. Reinsert code blocks
        codeBlocks.forEach((block, index) => {
            content = content.replace(`__CODE_BLOCK_${index}__`, block);
            // Handle edge case where block might have been wrapped in <p>
            content = content.replace(`<p>__CODE_BLOCK_${index}__</p>`, block);
        });

        return content;
    },

    /**
     * Copy code block contents to clipboard.
     */
    async copyCode(button) {
        const wrapper = button.closest(".code-block-wrapper");
        if (!wrapper) return;
        const codeElement = wrapper.querySelector("code");
        if (!codeElement) return;

        const codeText = codeElement.innerText;

        try {
            await navigator.clipboard.writeText(codeText);
            const originalHTML = button.innerHTML;
            button.innerHTML = `<i class="fa-solid fa-check"></i> <span>Copied!</span>`;
            button.style.color = "#10b981";

            setTimeout(() => {
                button.innerHTML = originalHTML;
                button.style.color = "";
            }, 2000);
        } catch (err) {
            console.error("Failed to copy code: ", err);
        }
    }
};

window.MarkdownParser = MarkdownParser;

