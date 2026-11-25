/**
 * SmartAI – Personal AI Assistant
 * Main Application Logic & User Interface Controller
 */

document.addEventListener("DOMContentLoaded", () => {
    // Application State
    const state = {
        currentConversationId: null,
        conversations: [],
        isGenerating: false,
        currentUser: null,
        theme: localStorage.getItem("smartai_theme") || "dark"
    };

    // DOM Elements Cache
    const elements = {
        // Layout
        sidebar: document.getElementById("sidebar"),
        sidebarToggleBtn: document.getElementById("sidebarToggleBtn"),
        mobileSidebarClose: document.getElementById("mobileSidebarClose"),
        sidebarBackdrop: document.getElementById("sidebarBackdrop"),
        themeToggleBtn: document.getElementById("themeToggleBtn"),
        themeLabel: document.getElementById("themeLabel"),

        // User Profile
        userNameDisplay: document.getElementById("userNameDisplay"),
        userEmailDisplay: document.getElementById("userEmailDisplay"),
        userAvatarInitial: document.getElementById("userAvatarInitial"),
        logoutBtn: document.getElementById("logoutBtn"),

        // Conversations
        newChatBtn: document.getElementById("newChatBtn"),
        conversationsList: document.getElementById("conversationsList"),
        searchChatsInput: document.getElementById("searchChatsInput"),
        currentChatTitle: document.getElementById("currentChatTitle"),
        clearChatBtn: document.getElementById("clearChatBtn"),
        chatModelBadge: document.getElementById("chatModelBadge"),

        // Status Card
        statusDot: document.getElementById("statusDot"),
        modelStatusName: document.getElementById("modelStatusName"),
        modelStatusSub: document.getElementById("modelStatusSub"),

        // Chat Area
        chatScrollContainer: document.getElementById("chatScrollContainer"),
        welcomeScreen: document.getElementById("welcomeScreen"),
        messagesContainer: document.getElementById("messagesContainer"),
        typingIndicator: document.getElementById("typingIndicator"),
        suggestionCards: document.querySelectorAll(".suggestion-card"),

        // Input
        messageInput: document.getElementById("messageInput"),
        sendBtn: document.getElementById("sendBtn"),
        toastContainer: document.getElementById("toastContainer")
    };

    /* ==========================================================================
       1. Theme Management
       ========================================================================== */
    function applyTheme(theme) {
        state.theme = theme;
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("smartai_theme", theme);
        elements.themeLabel.textContent = theme === "dark" ? "Dark Mode" : "Light Mode";
    }

    elements.themeToggleBtn.addEventListener("click", () => {
        const newTheme = state.theme === "dark" ? "light" : "dark";
        applyTheme(newTheme);
    });

    applyTheme(state.theme);

    /* ==========================================================================
       2. Responsive Sidebar Controls
       ========================================================================== */
    function toggleSidebar(forceState) {
        const isOpen = forceState !== undefined ? forceState : elements.sidebar.classList.contains("open");
        if (isOpen) {
            elements.sidebar.classList.remove("open");
            elements.sidebarBackdrop.classList.remove("active");
        } else {
            elements.sidebar.classList.add("open");
            elements.sidebarBackdrop.classList.add("active");
        }
    }

    elements.sidebarToggleBtn.addEventListener("click", () => toggleSidebar());
    elements.mobileSidebarClose.addEventListener("click", () => toggleSidebar(true));
    elements.sidebarBackdrop.addEventListener("click", () => toggleSidebar(true));

    /* ==========================================================================
       3. System Status & Health Check
       ========================================================================== */
    async function checkSystemHealth() {
        try {
            const data = await API.getHealth();
            const engine = data.engine || {};
            
            elements.modelStatusName.textContent = engine.model_name || "HF Model";
            
            if (engine.is_loaded) {
                elements.statusDot.className = "status-indicator-dot online";
                elements.modelStatusSub.textContent = `Ready (${engine.device.toUpperCase()})`;
                elements.chatModelBadge.textContent = `${engine.model_name.split("/").pop()} • ${engine.device.toUpperCase()}`;
            } else if (engine.is_loading) {
                elements.statusDot.className = "status-indicator-dot";
                elements.modelStatusSub.textContent = "Loading weights...";
                elements.chatModelBadge.textContent = "Loading Model...";
            } else {
                elements.statusDot.className = "status-indicator-dot online";
                elements.modelStatusSub.textContent = `Standby (${engine.device.toUpperCase()})`;
                elements.chatModelBadge.textContent = `${engine.model_name.split("/").pop()} • Ready`;
            }
        } catch (error) {
            elements.statusDot.className = "status-indicator-dot offline";
            elements.modelStatusName.textContent = "Backend Offline";
            elements.modelStatusSub.textContent = "Check terminal";
        }
    }

    /* ==========================================================================
       4. Conversations Management
       ========================================================================== */
    async function loadConversations() {
        try {
            const data = await API.getConversations();
            state.conversations = data.conversations || [];
            renderConversationsList();
        } catch (error) {
            showToast("Failed to load conversation history.", "error");
        }
    }

    function renderConversationsList(filterQuery = "") {
        elements.conversationsList.innerHTML = "";

        const query = filterQuery.toLowerCase().trim();
        const filtered = state.conversations.filter(c => 
            c.title.toLowerCase().includes(query) || (c.preview_message && c.preview_message.toLowerCase().includes(query))
        );

        if (filtered.length === 0) {
            elements.conversationsList.innerHTML = `
                <div class="empty-history-text">
                    ${query ? "No matching chats found." : "No conversations yet.<br>Start a new chat!"}
                </div>
            `;
            return;
        }

        filtered.forEach(conv => {
            const item = document.createElement("div");
            item.className = `conv-item ${conv.id === state.currentConversationId ? "active" : ""}`;
            item.dataset.id = conv.id;

            item.innerHTML = `
                <div class="conv-item-left">
                    <i class="fa-regular fa-message"></i>
                    <span class="conv-title" title="${escapeText(conv.title)}">${escapeText(conv.title)}</span>
                </div>
                <button class="conv-delete-btn" title="Delete chat">
                    <i class="fa-regular fa-trash-can"></i>
                </button>
            `;

            // Select conversation click
            item.addEventListener("click", (e) => {
                if (e.target.closest(".conv-delete-btn")) return;
                selectConversation(conv.id);
                if (window.innerWidth <= 768) toggleSidebar(true);
            });

            // Delete conversation click
            const delBtn = item.querySelector(".conv-delete-btn");
            delBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (confirm(`Delete "${conv.title}"?`)) {
                    await deleteConversation(conv.id);
                }
            });

            elements.conversationsList.appendChild(item);
        });
    }

    elements.searchChatsInput.addEventListener("input", (e) => {
        renderConversationsList(e.target.value);
    });

    async function selectConversation(convId) {
        if (state.isGenerating) return;

        try {
            state.currentConversationId = convId;
            renderConversationsList(elements.searchChatsInput.value);

            const data = await API.getConversation(convId);
            const conv = data.conversation;

            elements.currentChatTitle.textContent = conv.title || "Chat";
            renderMessages(conv.messages || []);
        } catch (error) {
            showToast("Failed to load chat conversation.", "error");
        }
    }

    async function deleteConversation(convId) {
        try {
            await API.deleteConversation(convId);
            state.conversations = state.conversations.filter(c => c.id !== convId);

            if (state.currentConversationId === convId) {
                startNewChat();
            } else {
                renderConversationsList(elements.searchChatsInput.value);
            }
            showToast("Conversation deleted.", "success");
        } catch (error) {
            showToast("Error deleting conversation.", "error");
        }
    }

    function startNewChat() {
        if (state.isGenerating) return;

        state.currentConversationId = null;
        elements.currentChatTitle.textContent = "New Chat";
        elements.messagesContainer.innerHTML = "";
        elements.welcomeScreen.style.display = "flex";
        renderConversationsList(elements.searchChatsInput.value);
        elements.messageInput.value = "";
        adjustTextareaHeight();
        elements.messageInput.focus();

        if (window.innerWidth <= 768) toggleSidebar(true);
    }

    elements.newChatBtn.addEventListener("click", startNewChat);

    // Clear Chat in active conversation
    elements.clearChatBtn.addEventListener("click", async () => {
        if (!state.currentConversationId) {
            elements.messagesContainer.innerHTML = "";
            elements.welcomeScreen.style.display = "flex";
            return;
        }

        if (confirm("Clear all messages in this conversation?")) {
            try {
                await API.clearConversation(state.currentConversationId);
                elements.messagesContainer.innerHTML = "";
                elements.welcomeScreen.style.display = "flex";
                showToast("Chat messages cleared.", "success");
            } catch (error) {
                showToast("Failed to clear chat.", "error");
            }
        }
    });

    // Keyboard shortcut Ctrl+K / Cmd+K
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
            e.preventDefault();
            startNewChat();
        }
    });

    /* ==========================================================================
       5. Message Rendering & Actions
       ========================================================================== */
    function renderMessages(messages) {
        elements.messagesContainer.innerHTML = "";

        if (messages.length === 0) {
            elements.welcomeScreen.style.display = "flex";
            return;
        }

        elements.welcomeScreen.style.display = "none";

        messages.forEach(msg => {
            appendMessageBubble(msg.sender, msg.content, msg.id, false);
        });

        scrollToBottom();
    }

    function appendMessageBubble(sender, content, messageId = null, scroll = true) {
        elements.welcomeScreen.style.display = "none";

        const isUser = sender === "user";
        const row = document.createElement("div");
        row.className = `message-row ${isUser ? "user-row" : "assistant-row"}`;
        if (messageId) row.dataset.id = messageId;

        const avatarIcon = isUser ? `<i class="fa-solid fa-user"></i>` : `<i class="fa-solid fa-sparkles"></i>`;
        const avatarClass = isUser ? "user-avatar" : "assistant-avatar";

        // Render content
        let bubbleContentHtml = "";
        if (isUser) {
            bubbleContentHtml = escapeText(content).replace(/\n/g, "<br>");
        } else {
            bubbleContentHtml = `<div class="markdown-body">${MarkdownParser.render(content)}</div>`;
        }

        // Assistant action toolbar (Copy, Regenerate)
        let actionsHtml = "";
        if (!isUser) {
            actionsHtml = `
                <div class="message-actions">
                    <button class="msg-action-btn copy-msg-btn" title="Copy response">
                        <i class="fa-regular fa-copy"></i>
                        <span>Copy</span>
                    </button>
                    <button class="msg-action-btn regen-msg-btn" title="Regenerate response">
                        <i class="fa-solid fa-rotate-right"></i>
                        <span>Regenerate</span>
                    </button>
                </div>
            `;
        }

        row.innerHTML = `
            <div class="message-avatar ${avatarClass}">
                ${avatarIcon}
            </div>
            <div class="message-content-wrapper">
                <div class="message-bubble">
                    ${bubbleContentHtml}
                </div>
                ${actionsHtml}
            </div>
        `;

        // Wire copy action
        if (!isUser) {
            const copyBtn = row.querySelector(".copy-msg-btn");
            if (copyBtn) {
                copyBtn.addEventListener("click", async () => {
                    try {
                        await navigator.clipboard.writeText(content);
                        const originalHTML = copyBtn.innerHTML;
                        copyBtn.innerHTML = `<i class="fa-solid fa-check"></i> <span>Copied!</span>`;
                        setTimeout(() => copyBtn.innerHTML = originalHTML, 2000);
                        showToast("Response copied to clipboard!", "success");
                    } catch (e) {
                        showToast("Failed to copy response.", "error");
                    }
                });
            }

            // Wire regenerate action
            const regenBtn = row.querySelector(".regen-msg-btn");
            if (regenBtn) {
                regenBtn.addEventListener("click", () => handleRegenerate());
            }
        }

        elements.messagesContainer.appendChild(row);

        if (scroll) {
            scrollToBottom();
        }

        return row;
    }

    function scrollToBottom() {
        setTimeout(() => {
            elements.chatScrollContainer.scrollTop = elements.chatScrollContainer.scrollHeight;
        }, 50);
    }

    function setGeneratingState(generating) {
        state.isGenerating = generating;
        elements.sendBtn.disabled = generating || !elements.messageInput.value.trim();
        elements.messageInput.disabled = generating;
        elements.typingIndicator.style.display = generating ? "flex" : "none";

        if (generating) {
            elements.sendBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
            scrollToBottom();
        } else {
            elements.sendBtn.innerHTML = `<i class="fa-solid fa-arrow-up"></i>`;
            elements.messageInput.focus();
        }
    }

    /* ==========================================================================
       6. Sending & Generating Messages
       ========================================================================== */
    async function handleSendMessage() {
        const messageText = elements.messageInput.value.trim();
        if (!messageText || state.isGenerating) return;

        // Clear input and adjust height
        elements.messageInput.value = "";
        adjustTextareaHeight();

        // Append user message immediately to the UI
        appendMessageBubble("user", messageText);
        setGeneratingState(true);

        try {
            const data = await API.sendMessage(state.currentConversationId, messageText);
            
            // If new conversation was created on the backend
            if (!state.currentConversationId) {
                state.currentConversationId = data.conversation_id;
                elements.currentChatTitle.textContent = data.title;
                await loadConversations();
            }

            // Append assistant response
            if (data.assistant_message) {
                appendMessageBubble("assistant", data.assistant_message.content, data.assistant_message.id);
            }

        } catch (error) {
            showToast(error.message || "Failed to generate response. Check model status.", "error");
            appendMessageBubble("assistant", `⚠️ **Error:** ${error.message || "Failed to generate response. Please ensure the local Hugging Face model or API is configured correctly."}`);
        } finally {
            setGeneratingState(false);
        }
    }

    async function handleRegenerate() {
        if (!state.currentConversationId || state.isGenerating) return;

        // Remove the last assistant message from DOM
        const rows = elements.messagesContainer.querySelectorAll(".assistant-row");
        if (rows.length > 0) {
            const lastRow = rows[rows.length - 1];
            lastRow.remove();
        }

        setGeneratingState(true);

        try {
            const data = await API.regenerate(state.currentConversationId);
            if (data.assistant_message) {
                appendMessageBubble("assistant", data.assistant_message.content, data.assistant_message.id);
            }
        } catch (error) {
            showToast(error.message || "Regeneration failed.", "error");
        } finally {
            setGeneratingState(false);
        }
    }

    /* ==========================================================================
       7. Input Handling & Suggestions
       ========================================================================== */
    function adjustTextareaHeight() {
        elements.messageInput.style.height = "auto";
        const newHeight = Math.min(elements.messageInput.scrollHeight, 180);
        elements.messageInput.style.height = `${newHeight}px`;

        const hasText = !!elements.messageInput.value.trim();
        elements.sendBtn.disabled = !hasText || state.isGenerating;
    }

    elements.messageInput.addEventListener("input", adjustTextareaHeight);

    elements.messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    elements.sendBtn.addEventListener("click", handleSendMessage);

    // Suggestion Cards click
    elements.suggestionCards.forEach(card => {
        card.addEventListener("click", () => {
            const prompt = card.dataset.prompt;
            if (prompt) {
                elements.messageInput.value = prompt;
                adjustTextareaHeight();
                handleSendMessage();
            }
        });
    });

    /* ==========================================================================
       8. Utility Helpers
       ========================================================================== */
    function escapeText(str) {
        if (!str) return "";
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        
        let icon = "fa-circle-info";
        if (type === "success") icon = "fa-circle-check";
        if (type === "error") icon = "fa-triangle-exclamation";

        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${escapeText(message)}</span>
        `;

        elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(10px)";
            setTimeout(() => toast.remove(), 250);
        }, 3200);
    }

    /* ==========================================================================
       8.5. User Profile & Authentication
       ========================================================================== */
    async function checkCurrentUser() {
        try {
            const data = await API.getCurrentUser();
            if (data && data.success && data.user) {
                state.currentUser = data.user;
                if (elements.userNameDisplay) elements.userNameDisplay.textContent = data.user.name;
                if (elements.userEmailDisplay) elements.userEmailDisplay.textContent = data.user.email;
                if (elements.userAvatarInitial) elements.userAvatarInitial.textContent = data.user.name.charAt(0).toUpperCase();
            } else {
                window.location.href = "/login";
            }
        } catch (err) {
            console.warn("User not authenticated, redirecting to login...");
            window.location.href = "/login";
        }
    }

    if (elements.logoutBtn) {
        elements.logoutBtn.addEventListener("click", async () => {
            if (confirm("Are you sure you want to log out of SmartAI?")) {
                try {
                    await API.logout();
                } catch (e) {
                    console.error("Logout error:", e);
                }
                window.location.href = "/login";
            }
        });
    }

    /* ==========================================================================
       9. App Initialization
       ========================================================================== */
    async function init() {
        await checkCurrentUser();
        await checkSystemHealth();
        await loadConversations();
        elements.messageInput.focus();
        
        // Periodic subtle health check every 45s
        setInterval(checkSystemHealth, 45000);
    }

    init();
});

