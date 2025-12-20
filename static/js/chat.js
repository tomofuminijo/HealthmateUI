// Chat functionality with htmx integration
class ChatInterface {
    constructor() {
        // DOM elements
        const elements = {
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-button'),
            sendText: document.getElementById('send-text'),
            sendSpinner: document.getElementById('send-spinner'),
            charCounter: document.getElementById('char-counter'),
            connectionError: document.getElementById('connection-error'),
            statusIndicator: document.getElementById('status-indicator')
        };
        
        this.chatForm = document.getElementById('chat-form');
        this.chatMessages = document.getElementById('chat-messages');
        
        // Initialize modules
        this.sessionManager = new SessionManager();
        this.uiManager = new UIManager(elements);
        this.messageManager = new MessageManager(this.chatMessages);
        this.streamingManager = new StreamingManager(this.chatMessages);
        this.historyManager = new HistoryManager(this.messageManager, this.sessionManager);
        
        // Set up callbacks
        this.uiManager.onSubmitMessage = () => this.handleFormSubmit();
        this.uiManager.onClearChat = () => this.historyManager.clearChat();
        this.streamingManager.onError = (message) => this.messageManager.addErrorMessage(message);
        
        // Override streaming manager methods that need access to message manager
        this.streamingManager.createMessageElement = (content, sender) => 
            this.messageManager.createMessageElement(content, sender);
        this.streamingManager.scrollToBottom = () => this.messageManager.scrollToBottom();
        this.streamingManager.smartScrollToBottom = () => this.messageManager.smartScrollToBottom();
        
        this.init();
    }

    async init() {
        // Initialize session first
        await this.sessionManager.initialize();
        
        // Check authentication status first
        this.checkAuthenticationStatus();
        
        // New chat button
        document.getElementById('new-chat-btn').addEventListener('click', () => {
            this.historyManager.startNewChatSession();
        });
        
        // Chat form submission
        this.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit();
        });
        
        // Initialize streaming connection
        this.initializeStreaming();
        
        // Set initial focus
        setTimeout(() => {
            this.uiManager.messageInput.focus();
        }, 100);
        
        // Initial send button state
        this.uiManager.updateSendButtonState();
        
        // Update history loading URL with session ID
        this.historyManager.updateHistoryLoadingUrl();
        
        // Load initial chat history (delay to ensure session is initialized)
        setTimeout(() => {
            this.historyManager.loadInitialHistory();
        }, 1000);
    }

    checkAuthenticationStatus() {
        // Check if we have authentication cookies
        const hasAuthCookie = document.cookie.includes('healthmate_session');
        
        if (!hasAuthCookie) {
            console.warn('No authentication cookie found - user may not be logged in');
            // Don't redirect immediately, let the API call handle it
        }
    }
    
    initializeStreaming() {
        // Streaming is now handled through the unified /api/chat/send endpoint
        // No persistent connection needed
        console.log('Streaming initialized - using unified API');
    }
    
    async handleFormSubmit() {
        const messageText = this.uiManager.getCurrentMessage();
        if (!messageText) {
            return;
        }
        
        // Disable input during submission
        this.uiManager.setInputDisabled(true);
        
        // Add user message to chat display
        this.messageManager.addUserMessage(messageText);
        
        // Clear input field and maintain focus
        this.uiManager.clearInputAndMaintainFocus();
        
        try {
            // Use unified chat API with streaming
            const formData = new FormData();
            formData.append('message', messageText);
            formData.append('timezone', 'Asia/Tokyo');
            formData.append('language', 'ja');
            formData.append('stream', 'true');
            
            // Add session ID for continuity
            const sessionId = this.sessionManager.getCurrentSessionId();
            if (sessionId) {
                formData.append('session_id', sessionId);
            }
            
            const response = await fetch('/api/chat/send', {
                method: 'POST',
                credentials: 'include',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Process Server-Sent Events
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            // Start streaming display
            this.streamingManager.startStreaming();
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) {
                    break;
                }
                
                // Add to buffer
                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;
                
                // Process complete lines
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const eventData = JSON.parse(line.slice(6));
                            this.streamingManager.handleStreamingEvent(eventData);
                        } catch (e) {
                            console.error('Error parsing SSE data:', e, 'Line:', line);
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error('Message sending error:', error);
            this.messageManager.addErrorMessage(`メッセージ送信エラー: ${error.message}`);
        } finally {
            // Re-enable input
            this.uiManager.setInputDisabled(false);
            
            if (this.streamingManager.getIsStreaming()) {
                this.streamingManager.completeStreaming();
            }
        }
    }
    
    destroy() {
        // Cleanup method for page unload
        console.log('ChatInterface destroyed');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatInterface;
} else {
    window.ChatInterface = ChatInterface;
}