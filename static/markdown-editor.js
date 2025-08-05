// Markdown Editor Component
class MarkdownEditor {
    constructor(textareaId, previewId = null) {
        this.textarea = document.getElementById(textareaId);
        this.preview = previewId ? document.getElementById(previewId) : null;
        this.init();
    }

    init() {
        if (!this.textarea) return;

        // Check if toolbar already exists
        if (this.textarea.parentNode.querySelector('.markdown-toolbar')) {
            return; // Toolbar already exists, don't create another one
        }

        // Create toolbar
        this.createToolbar();
        
        // Add event listeners
        this.textarea.addEventListener('input', () => this.updatePreview());
        this.textarea.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // Initial preview update
        this.updatePreview();
    }

    createToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'markdown-toolbar';
        toolbar.innerHTML = `
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="bold" title="Bold (Ctrl+B)">
                <strong>B</strong>
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="italic" title="Italic (Ctrl+I)">
                <em>I</em>
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="underline" title="Underline (Ctrl+U)">
                <u>U</u>
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="heading" title="Heading">
                H
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="link" title="Link">
                🔗
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="list-ul" title="Unordered List">
                • List
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="list-ol" title="Ordered List">
                1. List
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="code" title="Inline Code">
                &lt;/&gt;
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="code-block" title="Code Block">
                📝
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="quote" title="Quote">
                "
            </button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-action="preview" title="Toggle Preview">
                👁
            </button>
        `;

        // Insert toolbar before textarea
        this.textarea.parentNode.insertBefore(toolbar, this.textarea);

        // Add event listeners to toolbar buttons
        toolbar.addEventListener('click', (e) => {
            if (e.target.closest('button')) {
                const action = e.target.closest('button').dataset.action;
                this.handleToolbarAction(action);
            }
        });
    }

    handleToolbarAction(action) {
        const start = this.textarea.selectionStart;
        const end = this.textarea.selectionEnd;
        const text = this.textarea.value;
        const selectedText = text.substring(start, end);

        let replacement = '';
        let cursorOffset = 0;

        switch (action) {
            case 'bold':
                replacement = `**${selectedText}**`;
                cursorOffset = 2;
                break;
            case 'italic':
                replacement = `*${selectedText}*`;
                cursorOffset = 1;
                break;
            case 'underline':
                replacement = `__${selectedText}__`;
                cursorOffset = 2;
                break;
            case 'heading':
                replacement = `# ${selectedText}`;
                cursorOffset = 2;
                break;
            case 'link':
                const url = prompt('Enter URL:');
                if (url) {
                    replacement = `[${selectedText || 'Link Text'}](${url})`;
                    cursorOffset = selectedText ? 0 : -8;
                }
                break;
            case 'list-ul':
                replacement = `- ${selectedText}`;
                cursorOffset = 2;
                break;
            case 'list-ol':
                replacement = `1. ${selectedText}`;
                cursorOffset = 3;
                break;
            case 'code':
                replacement = `\`${selectedText}\``;
                cursorOffset = 1;
                break;
            case 'code-block':
                const language = prompt('Enter programming language (e.g., python, javascript, html):') || '';
                const codeBlock = language ? `\`\`\`${language}\n${selectedText}\n\`\`\`` : `\`\`\`\n${selectedText}\n\`\`\``;
                replacement = codeBlock;
                cursorOffset = language ? language.length + 4 : 4;
                break;
            case 'quote':
                replacement = `> ${selectedText}`;
                cursorOffset = 2;
                break;
            case 'preview':
                this.togglePreview();
                return;
        }

        if (replacement !== '') {
            this.textarea.value = text.substring(0, start) + replacement + text.substring(end);
            this.textarea.selectionStart = start + replacement.length + cursorOffset;
            this.textarea.selectionEnd = start + replacement.length + cursorOffset;
            this.textarea.focus();
            this.updatePreview();
        }
    }

    handleKeydown(e) {
        // Handle keyboard shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch (e.key.toLowerCase()) {
                case 'b':
                    e.preventDefault();
                    this.handleToolbarAction('bold');
                    break;
                case 'i':
                    e.preventDefault();
                    this.handleToolbarAction('italic');
                    break;
                case 'u':
                    e.preventDefault();
                    this.handleToolbarAction('underline');
                    break;
            }
        }
        
        // Handle tab key for code blocks
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.textarea.selectionStart;
            const end = this.textarea.selectionEnd;
            const text = this.textarea.value;
            
            // Check if we're inside a code block
            const beforeCursor = text.substring(0, start);
            const lines = beforeCursor.split('\n');
            const currentLine = lines[lines.length - 1];
            
            // If we're in a code block, insert 4 spaces instead of tab
            if (this.isInCodeBlock(beforeCursor)) {
                const spaces = '    ';
                this.textarea.value = text.substring(0, start) + spaces + text.substring(end);
                this.textarea.selectionStart = start + spaces.length;
                this.textarea.selectionEnd = start + spaces.length;
            } else {
                // Regular tab behavior
                const tab = '    ';
                this.textarea.value = text.substring(0, start) + tab + text.substring(end);
                this.textarea.selectionStart = start + tab.length;
                this.textarea.selectionEnd = start + tab.length;
            }
            
            this.updatePreview();
        }
    }

    isInCodeBlock(text) {
        const lines = text.split('\n');
        let inCodeBlock = false;
        
        for (let i = lines.length - 1; i >= 0; i--) {
            const line = lines[i].trim();
            if (line.startsWith('```')) {
                inCodeBlock = !inCodeBlock;
            }
        }
        
        return inCodeBlock;
    }

    updatePreview() {
        if (!this.preview) return;

        // Enhanced markdown to HTML conversion for preview
        let html = this.textarea.value
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/__(.*?)__/g, '<u>$1</u>')
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/^\- (.*$)/gm, '<li>$1</li>')
            .replace(/^\d+\. (.*$)/gm, '<li>$1</li>')
            .replace(/`(.*?)`/g, '<code class="inline-code">$1</code>')
            .replace(/^> (.*$)/gm, '<blockquote>$1</blockquote>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
            .replace(/\n/g, '<br>');

        // Handle code blocks with syntax highlighting
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, language, code) => {
            const lang = language || 'text';
            const escapedCode = code
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
            
            return `<pre class="code-block"><code class="language-${lang}">${escapedCode}</code></pre>`;
        });

        // Wrap lists
        html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        
        this.preview.innerHTML = html;
        
        // Apply syntax highlighting if Prism.js is available
        if (typeof Prism !== 'undefined') {
            Prism.highlightAllUnder(this.preview);
        }
    }

    togglePreview() {
        if (!this.preview) return;
        
        const isVisible = this.preview.style.display !== 'none';
        this.preview.style.display = isVisible ? 'none' : 'block';
        this.textarea.style.display = isVisible ? 'block' : 'none';
    }

    getValue() {
        return this.textarea.value;
    }

    setValue(value) {
        this.textarea.value = value;
        this.updatePreview();
    }
}

// Initialize markdown editors when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Auto-initialize markdown editors
    const markdownTextareas = document.querySelectorAll('.markdown-editor');
    markdownTextareas.forEach(textarea => {
        // Check if this textarea already has a markdown editor
        if (textarea.dataset.markdownInitialized) {
            return; // Already initialized
        }
        
        const previewId = textarea.dataset.preview;
        new MarkdownEditor(textarea.id, previewId);
        
        // Mark as initialized to prevent duplicate initialization
        textarea.dataset.markdownInitialized = 'true';
    });
}); 