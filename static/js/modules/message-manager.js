/**
 * Message Management Module
 * Handles message creation, display, and scrolling
 */
class MessageManager {
    constructor(chatMessages) {
        this.chatMessages = chatMessages;
    }

    addUserMessage(content) {
        const messageDiv = this.createMessageElement(content, 'user');
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom(); // Always scroll for user messages
    }

    addAssistantMessage(content) {
        const messageDiv = this.createMessageElement(content, 'assistant');
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom(); // Always scroll for complete assistant messages
    }

    addErrorMessage(content) {
        const messageDiv = this.createMessageElement(content, 'error');
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom(); // Always scroll for error messages
    }

    createMessageElement(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3';
        
        const isUser = sender === 'user';
        const isError = sender === 'error';
        const timestamp = new Date().toLocaleTimeString('ja-JP', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        let bgColor, icon;
        if (isUser) {
            bgColor = 'bg-blue-100';
            icon = '👤';
        } else if (isError) {
            bgColor = 'bg-red-100';
            icon = '⚠️';
        } else {
            bgColor = 'bg-gray-100';
            icon = '🤖';
        }
        
        // Escape HTML and convert newlines to <br> tags (consistent with chat_history.html)
        const escapedContent = this.escapeHtml(content).replace(/\n/g, '<br>');
        
        messageDiv.innerHTML = `
            <div class="w-8 h-8 ${isUser ? 'bg-gray-400' : isError ? 'bg-red-500' : 'bg-blue-500'} rounded-full flex items-center justify-center flex-shrink-0">
                <span class="text-white text-sm">${icon}</span>
            </div>
            <div class="flex-1">
                <div class="${bgColor} rounded-lg px-4 py-2">
                    <p class="text-gray-900 leading-relaxed">${escapedContent}</p>
                </div>
                <p class="text-xs text-gray-500 mt-1">${timestamp}</p>
            </div>
        `;
        
        return messageDiv;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    // Smart scroll: only auto-scroll if user is near the bottom
    smartScrollToBottom() {
        const container = this.chatMessages;
        const threshold = 70; // pixels from bottom to consider "at bottom" - balanced threshold
        
        // Check if user is near the bottom
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight <= threshold;
        
        if (isNearBottom) {
            this.scrollToBottom();
        }
        // If user is not at bottom, don't auto-scroll (let them read)
    }

    clearMessages() {
        this.chatMessages.innerHTML = '';
    }

    showLoadingIndicator(message = 'チャット履歴を読み込み中...') {
        this.chatMessages.innerHTML = `
            <div class="flex items-center justify-center py-8">
                <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                <span class="ml-2 text-gray-500">${message}</span>
            </div>
        `;
    }

    showWelcomeMessage() {
        this.chatMessages.innerHTML = `
            <div class="flex items-start space-x-3 mb-4 animate-fade-in">
                <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm">
                    <span class="text-white text-sm">🤖</span>
                </div>
                <div class="flex-1 max-w-3xl">
                    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg px-4 py-3 shadow-sm">
                        <div class="text-gray-900 leading-relaxed">
                            <p class="font-medium text-blue-900 mb-2">こんにちは！HealthCoach AIです 👋</p>
                            <p class="text-gray-700">
                                あなたの健康目標達成をサポートします。<br>
                                何かご質問やご相談はありますか？
                            </p>
                            <div class="mt-3 text-sm text-gray-600">
                                <p>💡 例えば：</p>
                                <ul class="list-disc list-inside mt-1 space-y-1 text-xs">
                                    <li>「健康的な食事のアドバイスをください」</li>
                                    <li>「運動習慣を始めたいです」</li>
                                    <li>「睡眠の質を改善したいです」</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                    <p class="text-xs text-gray-500 mt-2">今</p>
                </div>
            </div>
        `;
        
        this.scrollToBottom();
    }

    showAuthenticationError() {
        this.chatMessages.innerHTML = `
            <div class="flex items-center justify-center py-8">
                <div class="text-center">
                    <div class="text-red-500 mb-4">
                        <svg class="w-12 h-12 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 15.5c-.77.833.192 2.5 1.732 2.5z"></path>
                        </svg>
                        <h3 class="text-lg font-medium">認証が必要です</h3>
                    </div>
                    <p class="text-gray-600 mb-4">チャット履歴を表示するにはログインが必要です。</p>
                    <button onclick="window.location.href='/login'" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg">
                        ログインページへ
                    </button>
                </div>
            </div>
        `;
    }

    setContent(html) {
        this.chatMessages.innerHTML = html;
        this.scrollToBottom();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MessageManager;
} else {
    window.MessageManager = MessageManager;
}