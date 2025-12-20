/**
 * Streaming Management Module
 * Handles real-time streaming of AI responses
 */
class StreamingManager {
    constructor(chatMessages) {
        this.chatMessages = chatMessages;
        this.streamingResponse = null;
        this.streamingText = null;
        this.typingIndicator = null;
        this.thinkingIndicator = null;
        this.isStreaming = false;
    }

    handleStreamingEvent(eventData) {
        switch (eventData.event_type) {
            case 'connected':
                break;
                
            case 'user_message':
                break;
                
            case 'ai_thinking':
                // AI is thinking - no status display needed
                break;
                
            case 'chunk':
                // Handle chunk events from the unified API
                const text = eventData.text;
                if (text) {
                    // Ensure streaming is started
                    if (!this.isStreaming) {
                        this.startStreaming();
                    }
                    
                    // Hide thinking indicator and show streaming text on first chunk
                    if (this.thinkingIndicator && !this.thinkingIndicator.classList.contains('hidden')) {
                        this.thinkingIndicator.classList.add('hidden');
                        this.streamingText.classList.remove('hidden');
                        this.typingIndicator.classList.remove('hidden');
                    }
                    
                    this.streamingText.textContent += text;
                    this.smartScrollToBottom();
                }
                break;
                
            case 'ai_message_complete':
                break;
                
            case 'complete':
                this.completeStreaming();
                break;
                
            case 'error':
                console.error('Streaming error:', eventData.error);
                this.onError(`エラー: ${eventData.error}`);
                this.completeStreaming();
                break;
                
            case 'disconnected':
                break;
                
            default:
                console.warn('Unknown streaming event type:', eventData.event_type);
        }
    }

    startStreaming() {
        this.isStreaming = true;
        
        // Create streaming response element in the chat messages area
        this.streamingResponse = document.createElement('div');
        this.streamingResponse.className = 'flex items-start space-x-3';
        this.streamingResponse.innerHTML = `
            <div class="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center flex-shrink-0">
                <span class="text-white text-sm">🤖</span>
            </div>
            <div class="flex-1">
                <div class="bg-gray-100 rounded-lg px-4 py-2">
                    <div id="thinking-indicator" class="flex items-center space-x-2 text-gray-600">
                        <span class="text-sm">🤔</span>
                        <span class="text-sm">考え中</span>
                        <div class="flex space-x-1">
                            <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms;"></div>
                            <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms;"></div>
                            <div class="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms;"></div>
                        </div>
                    </div>
                    <p id="streaming-text" class="text-gray-900 whitespace-pre-wrap hidden"></p>
                    <div id="typing-indicator" class="inline-block w-2 h-4 bg-blue-500 animate-pulse hidden"></div>
                </div>
            </div>
        `;
        
        // Add to chat messages area
        this.chatMessages.appendChild(this.streamingResponse);
        
        // Get references to the created elements
        this.streamingText = document.getElementById('streaming-text');
        this.typingIndicator = document.getElementById('typing-indicator');
        this.thinkingIndicator = document.getElementById('thinking-indicator');
        
        this.scrollToBottom();
    }

    completeStreaming() {
        this.isStreaming = false;
        
        if (this.typingIndicator) {
            this.typingIndicator.style.display = 'none';
        }
        
        // Convert streaming response to permanent message
        const finalText = this.streamingText ? this.streamingText.textContent : '';
        if (finalText && this.streamingResponse) {
            // Replace streaming response with permanent message
            const permanentMessage = this.createMessageElement(finalText, 'assistant');
            this.chatMessages.replaceChild(permanentMessage, this.streamingResponse);
        }
        
        // Clean up references
        this.streamingResponse = null;
        this.streamingText = null;
        this.typingIndicator = null;
        this.thinkingIndicator = null;
        
        this.scrollToBottom();
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

    // Callback functions (to be set by the main chat interface)
    onError(message) {
        // This will be overridden by the main chat interface
        console.error('Streaming error:', message);
    }

    getIsStreaming() {
        return this.isStreaming;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = StreamingManager;
} else {
    window.StreamingManager = StreamingManager;
}