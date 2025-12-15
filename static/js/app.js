// HealthmateUI Application JavaScript

// Global application state
window.HealthmateUI = {
    config: {
        apiBaseUrl: '/api',
        wsUrl: null, // Will be set dynamically
        debug: false
    },
    
    // Authentication state
    auth: {
        isAuthenticated: false,
        user: null,
        token: null
    },
    
    // Application utilities
    utils: {}
};

// Utility functions
HealthmateUI.utils = {
    /**
     * Format timestamp for display
     */
    formatTimestamp(date) {
        return new Intl.DateTimeFormat('ja-JP', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).format(date);
    },
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 p-4 rounded-md shadow-lg max-w-sm ${this.getNotificationClasses(type)}`;
        notification.innerHTML = `
            <div class="flex items-center">
                <span class="mr-2">${this.getNotificationIcon(type)}</span>
                <span class="flex-1">${this.escapeHtml(message)}</span>
                <button class="ml-2 text-gray-400 hover:text-gray-600" onclick="this.parentElement.parentElement.remove()">
                    ✕
                </button>
            </div>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    },
    
    getNotificationClasses(type) {
        const classes = {
            info: 'bg-blue-50 border border-blue-200 text-blue-800',
            success: 'bg-green-50 border border-green-200 text-green-800',
            warning: 'bg-yellow-50 border border-yellow-200 text-yellow-800',
            error: 'bg-red-50 border border-red-200 text-red-800'
        };
        return classes[type] || classes.info;
    },
    
    getNotificationIcon(type) {
        const icons = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '❌'
        };
        return icons[type] || icons.info;
    },
    
    /**
     * Make API request with error handling
     */
    async apiRequest(endpoint, options = {}) {
        const url = `${HealthmateUI.config.apiBaseUrl}${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };
        
        // Add auth token if available
        if (HealthmateUI.auth.token) {
            defaultOptions.headers['Authorization'] = `Bearer ${HealthmateUI.auth.token}`;
        }
        
        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                // Handle specific HTTP status codes
                if (response.status === 401) {
                    // Unauthorized - redirect to login
                    this.showNotification('セッションが期限切れです。再ログインしてください。', 'warning');
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                    throw new Error('Unauthorized');
                } else if (response.status === 403) {
                    throw new Error('アクセス権限がありません');
                } else if (response.status === 404) {
                    throw new Error('リソースが見つかりません');
                } else if (response.status >= 500) {
                    throw new Error('サーバーエラーが発生しました');
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }
            
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (error) {
            console.error('API request failed:', error);
            if (error.message !== 'Unauthorized') {
                this.showNotification(`API エラー: ${error.message}`, 'error');
            }
            throw error;
        }
    },

    /**
     * Make htmx-compatible API request
     */
    async htmxRequest(endpoint, options = {}) {
        const url = `${HealthmateUI.config.apiBaseUrl}${endpoint}`;
        
        // Set up htmx headers
        const headers = {
            'HX-Request': 'true',
            ...options.headers
        };
        
        return this.apiRequest(endpoint, { ...options, headers });
    },
    
    /**
     * Debounce function calls
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Authentication utilities
HealthmateUI.auth = {
    /**
     * Check if user is authenticated
     */
    async checkAuthStatus() {
        try {
            const response = await HealthmateUI.utils.apiRequest('/auth/status');
            this.isAuthenticated = response.authenticated;
            this.user = response.user;
            return this.isAuthenticated;
        } catch (error) {
            this.isAuthenticated = false;
            this.user = null;
            return false;
        }
    },
    
    /**
     * Logout user
     */
    async logout() {
        try {
            await HealthmateUI.utils.apiRequest('/auth/logout', { method: 'POST' });
            this.isAuthenticated = false;
            this.user = null;
            this.token = null;
            window.location.href = '/login';
        } catch (error) {
            console.error('Logout failed:', error);
            // Force logout even if API call fails
            window.location.href = '/login';
        }
    }
};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Set debug mode based on environment
    HealthmateUI.config.debug = document.body.dataset.debug === 'true';
    
    // Initialize htmx event listeners
    if (typeof htmx !== 'undefined') {
        // Global htmx configuration
        htmx.config.globalViewTransitions = true;
        htmx.config.scrollBehavior = 'smooth';
        htmx.config.defaultSwapStyle = 'innerHTML';
        htmx.config.defaultSwapDelay = 0;
        htmx.config.defaultSettleDelay = 20;
        
        // Add authentication headers to all htmx requests
        document.body.addEventListener('htmx:configRequest', function(evt) {
            if (HealthmateUI.auth.token) {
                evt.detail.headers['Authorization'] = `Bearer ${HealthmateUI.auth.token}`;
            }
            evt.detail.headers['HX-Request'] = 'true';
        });
        
        // Add loading indicators
        document.body.addEventListener('htmx:beforeRequest', function(evt) {
            const target = evt.target;
            
            // Add loading state to buttons
            if (target.tagName === 'BUTTON' || target.classList.contains('btn')) {
                target.classList.add('opacity-50', 'cursor-not-allowed');
                target.disabled = true;
            }
            
            // Add loading state to forms
            if (target.tagName === 'FORM') {
                const submitBtn = target.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    submitBtn.disabled = true;
                }
            }
            
            // Show global loading indicator for long requests
            setTimeout(() => {
                if (evt.detail.xhr.readyState !== 4) {
                    HealthmateUI.utils.showNotification('処理中...', 'info');
                }
            }, 1000);
        });
        
        document.body.addEventListener('htmx:afterRequest', function(evt) {
            const target = evt.target;
            
            // Remove loading state from buttons
            if (target.tagName === 'BUTTON' || target.classList.contains('btn')) {
                target.classList.remove('opacity-50', 'cursor-not-allowed');
                target.disabled = false;
            }
            
            // Remove loading state from forms
            if (target.tagName === 'FORM') {
                const submitBtn = target.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    submitBtn.disabled = false;
                }
            }
            
            // Handle successful responses
            if (evt.detail.successful) {
                // Auto-scroll to new content if needed
                const newContent = evt.detail.target;
                if (newContent && newContent.scrollIntoView) {
                    newContent.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
        });
        
        // Handle errors with detailed messages
        document.body.addEventListener('htmx:responseError', function(evt) {
            const status = evt.detail.xhr.status;
            let message = 'リクエストエラーが発生しました';
            
            if (status === 401) {
                message = 'セッションが期限切れです。再ログインしてください。';
                setTimeout(() => {
                    window.location.href = '/login';
                }, 2000);
            } else if (status === 403) {
                message = 'アクセス権限がありません';
            } else if (status === 404) {
                message = 'リソースが見つかりません';
            } else if (status >= 500) {
                message = 'サーバーエラーが発生しました';
            }
            
            HealthmateUI.utils.showNotification(message, 'error');
        });
        
        document.body.addEventListener('htmx:sendError', function(evt) {
            HealthmateUI.utils.showNotification('ネットワークエラーが発生しました。接続を確認してください。', 'error');
        });
        
        // Handle timeout
        document.body.addEventListener('htmx:timeout', function(evt) {
            HealthmateUI.utils.showNotification('リクエストがタイムアウトしました', 'warning');
        });
        
        // Handle validation errors
        document.body.addEventListener('htmx:validation:validate', function(evt) {
            // Custom validation logic can be added here
        });
        
        // Handle successful form submissions
        document.body.addEventListener('htmx:afterSettle', function(evt) {
            // Re-initialize any JavaScript components in new content
            const newContent = evt.target;
            if (newContent) {
                // Trigger custom initialization event
                newContent.dispatchEvent(new CustomEvent('healthmate:contentLoaded'));
            }
        });
    }
    
    // Initialize page-specific functionality
    const currentPage = window.location.pathname;
    
    if (currentPage === '/chat') {
        // Chat page initialization is handled in chat.html
    } else if (currentPage === '/login') {
        // Login page initialization is handled in login.html
    }
    
    // Global keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + K for quick search (future feature)
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            // TODO: Implement quick search
        }
        
        // Escape key to close modals
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal');
            modals.forEach(modal => {
                if (modal.style.display !== 'none') {
                    modal.style.display = 'none';
                }
            });
        }
    });
    
    console.log('HealthmateUI initialized');
});

// Service Worker registration (for future PWA support)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        // TODO: Register service worker when ready
        // navigator.serviceWorker.register('/sw.js');
    });
}