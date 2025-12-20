/**
 * History Management Module
 * Handles chat history loading and management
 */
class HistoryManager {
    constructor(messageManager, sessionManager) {
        this.messageManager = messageManager;
        this.sessionManager = sessionManager;
    }

    updateHistoryLoadingUrl() {
        // Update the htmx history loading URL to include current session ID
        const sessionId = this.sessionManager.getCurrentSessionId();
        if (sessionId) {
            const historyUrl = `/api/chat/history?session_id=${encodeURIComponent(sessionId)}`;
            this.messageManager.chatMessages.setAttribute('hx-get', historyUrl);
            console.log('Updated history loading URL:', historyUrl);
            console.log('Current session ID:', sessionId);
        }
    }

    async loadInitialHistory() {
        // Skip loading if this is a new session that was just created in this page load
        if (this.sessionManager.isNewSession()) {
            return;
        }
        
        // Wait for session ID to be initialized
        const sessionId = this.sessionManager.getCurrentSessionId();
        if (!sessionId) {
            console.log('Waiting for session ID to be initialized...');
            setTimeout(() => this.loadInitialHistory(), 500);
            return;
        }
        
        // Load initial chat history using fetch with session ID
        const historyUrl = `/api/chat/history?session_id=${encodeURIComponent(sessionId)}`;
        
        // Show loading indicator
        this.messageManager.showLoadingIndicator();
        
        // Use fetch to ensure cookies are included
        try {
            const response = await fetch(historyUrl, {
                method: 'GET',
                credentials: 'include',  // Include cookies
                headers: {
                    'HX-Request': 'true',
                    'Accept': 'text/html'
                }
            });

            if (response.ok) {
                const html = await response.text();
                this.messageManager.setContent(html);
            } else if (response.status === 401) {
                console.error('Authentication failed - user not logged in or session expired');
                this.messageManager.showAuthenticationError();
            } else {
                const errorText = await response.text();
                console.error('HTTP error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to load initial chat history:', error);
            
            // Show welcome message if no history or error
            this.showWelcomeMessage();
        }
    }

    async showWelcomeMessage() {
        // Clear messages and show welcome message directly
        const sessionId = this.sessionManager.getCurrentSessionId();
        console.log('Showing welcome message for session:', sessionId);
        
        this.messageManager.clearMessages();
        
        // Try to load empty history from server first, fallback to client-side message
        const emptyHistoryUrl = `/api/chat/history?session_id=${encodeURIComponent(sessionId)}`;
        console.log('Attempting to load empty history from server...');
        
        try {
            const response = await fetch(emptyHistoryUrl, {
                method: 'GET',
                credentials: 'include',  // Include cookies
                headers: {
                    'HX-Request': 'true',
                    'Accept': 'text/html'
                }
            });

            if (response.ok) {
                const html = await response.text();
                this.messageManager.setContent(html);
                console.log('Empty history loaded from server');
            } else if (response.status === 401) {
                console.log('Authentication error, redirecting to login');
                window.location.href = '/login';
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Failed to load empty history from server:', error);
            // Fallback to client-side welcome message
            this.messageManager.showWelcomeMessage();
        }
    }

    async clearChat() {
        if (confirm('チャット履歴をクリアしますか？この操作は元に戻せません。')) {
            // Clear the chat messages display
            this.messageManager.clearMessages();
            
            // Reset the session to start fresh
            await this.sessionManager.resetChatSession();
            await this.sessionManager.initialize();
            
            // Update the htmx history loading URL to use the new session ID
            this.updateHistoryLoadingUrl();
            
            console.log('Chat cleared and new session started');
        }
    }

    async startNewChatSession() {
        // Confirm with user before starting new session
        if (confirm('新しいチャットセッションを開始しますか？\n\n現在の会話は終了し、新しい会話セッションが始まります。\n（注意：あなたの長期記憶は保持されますが、現在のセッションの文脈はリセットされます）')) {
            // Clear the chat messages display
            this.messageManager.showLoadingIndicator('新しいセッションを開始中...');
            
            // Reset the session to start fresh
            const newSessionId = await this.sessionManager.startNewSession();
            
            // Update the htmx history loading URL to use the new session ID
            this.updateHistoryLoadingUrl();
            
            // Clear the chat messages and show welcome message immediately
            this.messageManager.clearMessages();
            this.messageManager.addAssistantMessage('新しいチャットセッションが開始されました！\n\n私はあなたの健康コーチAIです。過去の会話内容を覚えているので、継続的なサポートを提供できます。何かお手伝いできることはありますか？');
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = HistoryManager;
} else {
    window.HistoryManager = HistoryManager;
}