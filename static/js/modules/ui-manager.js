/**
 * UI Management Module
 * Handles input handling, UI state, and DOM manipulation
 */
class UIManager {
    constructor(elements) {
        this.messageInput = elements.messageInput;
        this.sendButton = elements.sendButton;
        this.sendText = elements.sendText;
        this.sendSpinner = elements.sendSpinner;
        this.charCounter = elements.charCounter;
        this.connectionError = elements.connectionError;
        this.statusIndicator = elements.statusIndicator;
        
        this.isComposing = false; // IME composition state
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // Auto-resize textarea
        this.messageInput.addEventListener('input', () => this.handleInput());
        
        // Character counter and send button state
        this.messageInput.addEventListener('input', () => {
            this.updateCharCounter();
            this.updateSendButtonState();
        });
        
        // Enter key handling
        this.messageInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // IME composition handling for Japanese input
        this.messageInput.addEventListener('compositionstart', () => {
            this.isComposing = true;
        });
        this.messageInput.addEventListener('compositionend', () => {
            this.isComposing = false;
        });
        
        // Focus management
        this.messageInput.addEventListener('focus', () => this.onInputFocus());
        this.messageInput.addEventListener('blur', () => this.onInputBlur());
        
        // Clear button
        document.getElementById('clear-input-btn').addEventListener('click', () => {
            this.clearInput();
        });
    }

    handleInput() {
        // Use requestAnimationFrame to ensure smooth cursor visibility
        requestAnimationFrame(() => {
            this.adjustTextareaHeight();
        });
    }

    handleKeyDown(e) {
        // Check if IME is composing (Japanese input conversion)
        if (this.isComposing || e.isComposing || e.keyCode === 229) {
            // During IME composition, don't handle Enter key
            return;
        }
        
        // Shift + Enter: Allow new line (don't prevent default)
        if (e.key === 'Enter' && e.shiftKey && !e.ctrlKey && !e.metaKey) {
            // Let the default behavior happen (insert new line)
            // Don't manually adjust height here - let the input event handle it
            return;
        }
        
        // Ctrl/Cmd + Enter: Force send message even with Shift
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            this.onSubmitMessage();
            return;
        }
        
        // Enter key: Send message (only if no modifier keys)
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            this.onSubmitMessage();
            return;
        }
        
        // Escape key: Clear input and focus
        if (e.key === 'Escape') {
            e.preventDefault();
            this.clearInput();
            this.messageInput.focus();
            return;
        }
        
        // Ctrl/Cmd + K: Clear chat
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            this.onClearChat();
            return;
        }
    }

    updateSendButtonState() {
        const hasText = this.messageInput.value.trim().length > 0;
        const isNotLoading = !this.sendButton.disabled;
        
        if (hasText && isNotLoading) {
            this.sendButton.classList.remove('opacity-50');
            this.sendButton.classList.add('hover:bg-blue-700');
        } else {
            this.sendButton.classList.add('opacity-50');
            this.sendButton.classList.remove('hover:bg-blue-700');
        }
    }

    onInputFocus() {
        // Visual feedback when input is focused
        this.messageInput.parentElement.classList.add('ring-2', 'ring-blue-500');
    }

    onInputBlur() {
        // Remove visual feedback when input loses focus
        this.messageInput.parentElement.classList.remove('ring-2', 'ring-blue-500');
    }

    adjustTextareaHeight() {
        // Save current state
        const cursorPosition = this.messageInput.selectionStart;
        const cursorEnd = this.messageInput.selectionEnd;
        const hasFocus = document.activeElement === this.messageInput;
        const currentHeight = this.messageInput.style.height;
        
        // Calculate new height without changing the current height first
        const tempElement = this.messageInput.cloneNode(true);
        tempElement.style.position = 'absolute';
        tempElement.style.visibility = 'hidden';
        tempElement.style.height = 'auto';
        tempElement.style.width = this.messageInput.offsetWidth + 'px';
        document.body.appendChild(tempElement);
        
        const newHeight = Math.min(tempElement.scrollHeight, 120);
        document.body.removeChild(tempElement);
        
        // Only update height if it actually changed
        if (currentHeight !== newHeight + 'px') {
            this.messageInput.style.height = newHeight + 'px';
        }
        
        // Force cursor visibility with a micro-delay
        if (hasFocus) {
            requestAnimationFrame(() => {
                this.messageInput.focus();
                this.messageInput.setSelectionRange(cursorPosition, cursorEnd);
                // Force a repaint to ensure cursor visibility
                this.messageInput.style.caretColor = 'transparent';
                requestAnimationFrame(() => {
                    this.messageInput.style.caretColor = '';
                });
            });
        }
    }

    updateCharCounter() {
        const length = this.messageInput.value.length;
        this.charCounter.textContent = `${length}/1000`;
        
        if (length > 900) {
            this.charCounter.classList.add('text-red-500');
        } else {
            this.charCounter.classList.remove('text-red-500');
        }
    }

    clearInput() {
        this.messageInput.value = '';
        this.updateCharCounter();
        this.adjustTextareaHeight();
        
        // Ensure input is enabled and focused
        this.setInputDisabled(false);
        
        // Focus the input field for next message
        setTimeout(() => {
            this.messageInput.focus();
            // Ensure cursor is positioned at the beginning
            this.messageInput.setSelectionRange(0, 0);
        }, 50);
    }

    clearInputAndMaintainFocus() {
        // Clear the input field
        this.messageInput.value = '';
        
        // Update character counter
        this.updateCharCounter();
        
        // Reset textarea height
        this.adjustTextareaHeight();
        
        // Maintain focus for next message
        // Use setTimeout to ensure the input is ready for focus
        setTimeout(() => {
            if (!this.messageInput.disabled) {
                this.messageInput.focus();
                // Ensure cursor is visible
                this.messageInput.setSelectionRange(0, 0);
            }
        }, 50);
        
        // Update send button state
        this.updateSendButtonState();
    }

    setInputDisabled(disabled) {
        this.messageInput.disabled = disabled;
        this.sendButton.disabled = disabled;
        
        if (disabled) {
            this.messageInput.classList.add('opacity-50', 'cursor-not-allowed');
            this.sendButton.classList.add('opacity-50', 'cursor-not-allowed');
        } else {
            this.messageInput.classList.remove('opacity-50', 'cursor-not-allowed');
            this.sendButton.classList.remove('opacity-50', 'cursor-not-allowed');
            // Restore focus after enabling
            setTimeout(() => {
                this.messageInput.focus();
            }, 100);
        }
    }

    setLoading(loading) {
        this.setInputDisabled(loading);
        
        if (loading) {
            this.sendText.textContent = '送信中...';
        } else {
            this.sendText.textContent = '送信';
        }
    }

    showConnectionError() {
        if (this.connectionError) {
            this.connectionError.classList.remove('hidden');
        }
        if (this.statusIndicator) {
            this.statusIndicator.classList.remove('hidden');
        }
    }

    hideConnectionError() {
        if (this.connectionError) {
            this.connectionError.classList.add('hidden');
        }
        if (this.statusIndicator) {
            this.statusIndicator.classList.add('hidden');
        }
    }

    getCurrentMessage() {
        return this.messageInput.value.trim();
    }

    // Callback functions (to be set by the main chat interface)
    onSubmitMessage() {
        // This will be overridden by the main chat interface
        console.log('Submit message callback not set');
    }

    onClearChat() {
        // This will be overridden by the main chat interface
        console.log('Clear chat callback not set');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UIManager;
} else {
    window.UIManager = UIManager;
}