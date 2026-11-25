/**
 * SmartAI - API Client
 * Centralized Fetch service for interacting with the Flask REST backend.
 * Handles authentication, user session, conversations, and LLM chat.
 */

const API = {
    baseUrl: "/api",

    /**
     * General request helper with error unwrapping and session 401 handling.
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultHeaders = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        };

        const config = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...options.headers
            }
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                // If unauthorized and on a protected page, redirect to login
                if (response.status === 401 && !endpoint.startsWith("/auth/")) {
                    const currentPath = window.location.pathname;
                    if (currentPath !== "/login" && currentPath !== "/signup") {
                        window.location.href = "/login";
                    }
                }

                const errorMessage = data.error || `HTTP error ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            return data;
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    },

    /* =========================================
       Authentication Endpoints
       ========================================= */

    /**
     * Sign up a new account.
     */
    async signup(name, email, password, confirmPassword) {
        return this.request("/auth/signup", {
            method: "POST",
            body: JSON.stringify({
                name,
                email,
                password,
                confirm_password: confirmPassword
            })
        });
    },

    /**
     * Log in to existing account.
     */
    async login(email, password, remember = true) {
        return this.request("/auth/login", {
            method: "POST",
            body: JSON.stringify({ email, password, remember })
        });
    },

    /**
     * Log out current user.
     */
    async logout() {
        return this.request("/auth/logout", {
            method: "POST"
        });
    },

    /**
     * Fetch profile of currently logged-in user.
     */
    async getCurrentUser() {
        return this.request("/auth/me", {
            method: "GET"
        });
    },

    /* =========================================
       System & Conversation Endpoints
       ========================================= */

    /**
     * Get system health and model status.
     */
    async getHealth() {
        return this.request("/health", { method: "GET" });
    },

    /**
     * List all conversation sessions for the authenticated user.
     */
    async getConversations() {
        return this.request("/conversations", { method: "GET" });
    },

    /**
     * Create a new conversation session.
     */
    async createConversation(title = "New Chat") {
        return this.request("/conversations", {
            method: "POST",
            body: JSON.stringify({ title })
        });
    },

    /**
     * Get a specific conversation and all messages.
     */
    async getConversation(id) {
        return this.request(`/conversations/${id}`, { method: "GET" });
    },

    /**
     * Delete a conversation.
     */
    async deleteConversation(id) {
        return this.request(`/conversations/${id}`, { method: "DELETE" });
    },

    /**
     * Clear all messages in a conversation.
     */
    async clearConversation(id) {
        return this.request(`/conversations/${id}/clear`, { method: "POST" });
    },

    /**
     * Send message and get AI response.
     */
    async sendMessage(conversationId, message) {
        return this.request("/chat", {
            method: "POST",
            body: JSON.stringify({
                conversation_id: conversationId,
                message: message
            })
        });
    },

    /**
     * Regenerate the last AI response.
     */
    async regenerate(conversationId) {
        return this.request("/chat/regenerate", {
            method: "POST",
            body: JSON.stringify({
                conversation_id: conversationId
            })
        });
    }
};

window.API = API;
