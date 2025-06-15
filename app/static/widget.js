// Finiite Chat Widget
function initFiniiteWidget(config) {
    const { agentId, baseUrl } = config;
    
    // Create widget styles
    const styles = document.createElement('style');
    styles.textContent = `
        #finiite-chat-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
        }
        
        .finiite-widget-container {
            display: flex;
            flex-direction: column;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: all 0.3s ease;
            height: 600px;
            width: 400px;
        }
        
        .finiite-widget-header {
            background: #007bff;
            color: white;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .finiite-widget-messages {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            display: flex;
            flex-direction: column;
        }
        
        .finiite-message {
            margin: 5px 0;
            padding: 10px;
            border-radius: 10px;
            max-width: 80%;
        }
        
        .finiite-message.user {
            background: #e9ecef;
            align-self: flex-end;
        }
        
        .finiite-message.agent {
            background: #007bff;
            color: white;
            align-self: flex-start;
        }
        
        .finiite-widget-input {
            padding: 15px;
            border-top: 1px solid #e9ecef;
            display: flex;
        }
        
        .finiite-widget-input input {
            flex: 1;
            padding: 8px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            margin-right: 10px;
        }
        
        .finiite-widget-input button {
            padding: 8px 15px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        
        .finiite-widget-input button:hover {
            background: #0056b3;
        }
        
        .finiite-widget-toggle {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 60px;
            height: 60px;
            border-radius: 30px;
            background: #007bff;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }
    `;
    document.head.appendChild(styles);

    // Create widget HTML
    const widgetContainer = document.createElement('div');
    widgetContainer.className = 'finiite-widget-container';
    widgetContainer.style.display = 'none';
    
    widgetContainer.innerHTML = `
        <div class="finiite-widget-header">
            <span>Chat with AI Assistant</span>
            <button onclick="toggleWidget()" style="background: none; border: none; color: white; cursor: pointer;">×</button>
        </div>
        <div class="finiite-widget-messages"></div>
        <div class="finiite-widget-input">
            <input type="text" placeholder="Type your message..." />
            <button onclick="sendMessage()">Send</button>
        </div>
    `;
    
    // Create toggle button
    const toggleButton = document.createElement('div');
    toggleButton.className = 'finiite-widget-toggle';
    toggleButton.innerHTML = '💬';
    toggleButton.onclick = toggleWidget;
    
    // Add elements to the page
    const widgetElement = document.getElementById('finiite-chat-widget');
    widgetElement.appendChild(widgetContainer);
    widgetElement.appendChild(toggleButton);
    
    // Widget state
    let isOpen = false;
    
    // Widget functions
    window.toggleWidget = function() {
        isOpen = !isOpen;
        widgetContainer.style.display = isOpen ? 'flex' : 'none';
        toggleButton.style.display = isOpen ? 'none' : 'flex';
    };
    
    window.sendMessage = async function() {
        const input = widgetContainer.querySelector('input');
        const message = input.value.trim();
        if (!message) return;
        
        // Clear input
        input.value = '';
        
        // Add user message to chat
        addMessage(message, 'user');
        
        try {
            // Send message to backend
            const response = await fetch(`${baseUrl}/chat/${agentId}/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    content: message,
                    model: 'gpt-3.5-turbo', // Default model
                }),
            });
            
            if (!response.ok) {
                throw new Error('Failed to send message');
            }
            
            const data = await response.json();
            
            // Add agent response to chat
            addMessage(data.content, 'agent');
            
        } catch (error) {
            console.error('Error sending message:', error);
            addMessage('Sorry, there was an error processing your message.', 'agent');
        }
    };
    
    function addMessage(content, role) {
        const messagesContainer = widgetContainer.querySelector('.finiite-widget-messages');
        const messageElement = document.createElement('div');
        messageElement.className = `finiite-message ${role}`;
        messageElement.textContent = content;
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    // Load initial configuration
    fetch(`${baseUrl}/chat/widget/${agentId}/config`)
        .then(response => response.json())
        .then(config => {
            // Update widget with configuration
            const header = widgetContainer.querySelector('.finiite-widget-header span');
            header.textContent = config.name || 'Chat with AI Assistant';
            
            // Add initial greeting if provided
            if (config.greeting) {
                addMessage(config.greeting, 'agent');
            }
            
            // Apply theme if provided
            if (config.theme === 'dark') {
                // Add dark theme styles
                styles.textContent += `
                    .finiite-widget-container {
                        background: #1a1a1a;
                        color: white;
                    }
                    .finiite-message.user {
                        background: #2d2d2d;
                        color: white;
                    }
                    .finiite-widget-input {
                        border-top: 1px solid #2d2d2d;
                    }
                    .finiite-widget-input input {
                        background: #2d2d2d;
                        color: white;
                        border: 1px solid #3d3d3d;
                    }
                `;
            }
            
            // Apply dimensions
            widgetContainer.style.height = config.height || '600px';
            widgetContainer.style.width = config.width || '400px';
        })
        .catch(error => {
            console.error('Error loading widget configuration:', error);
        });
}
