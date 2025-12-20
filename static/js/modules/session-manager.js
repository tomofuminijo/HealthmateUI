/**
 * Session Management Module
 * Handles chat session creation, storage, and management
 */
class SessionManager {
    constructor() {
        this.sessionId = null;
        this.isNewSessionJustCreated = false;
    }

    async initialize() {
        this.sessionId = await this.getOrCreateSessionId();
        console.log('Initialized session ID:', this.sessionId);
        return this.sessionId;
    }

    async getOrCreateSessionId() {
        // Session ID is now managed automatically by the unified API
        // Generate a client-side session ID for UI consistency
        let sessionId = localStorage.getItem('healthmate_chat_session_id');
        
        if (!sessionId) {
            // Generate a new session ID (must be at least 33 characters)
            const timestamp = Date.now().toString();
            const randomPart1 = Math.random().toString(36).substring(2, 17);
            const randomPart2 = Math.random().toString(36).substring(2, 17);
            sessionId = `healthmate-chat-${timestamp}-${randomPart1}-${randomPart2}`;
            
            // Ensure it's at least 33 characters
            while (sessionId.length < 33) {
                sessionId += Math.random().toString(36).substring(2, 3);
            }
            
            // Store in localStorage to share across tabs
            localStorage.setItem('healthmate_chat_session_id', sessionId);
        }
        
        return sessionId;
    }

    async resetChatSession() {
        // Clear the session ID to start a new conversation
        localStorage.removeItem('healthmate_chat_session_id');
        
        // Notify server to clear current session
        try {
            await fetch('/api/chat/clear-session', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
        } catch (error) {
            console.warn('Failed to clear session on server:', error);
        }
    }

    async startNewSession() {
        // Reset the session to start fresh
        await this.resetChatSession();
        this.sessionId = await this.getOrCreateSessionId();
        this.isNewSessionJustCreated = true;
        return this.sessionId;
    }

    getCurrentSessionId() {
        return this.sessionId;
    }

    isNewSession() {
        return this.isNewSessionJustCreated;
    }

    clearNewSessionFlag() {
        this.isNewSessionJustCreated = false;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SessionManager;
} else {
    window.SessionManager = SessionManager;
}