import { create } from 'zustand'

const useStore = create((set, get) => ({
  messages: [],
  agentStatus: 'idle',
  darkMode: localStorage.getItem('darkMode') === 'true',
  apiEndpoint: localStorage.getItem('apiEndpoint') || '',
  conversations: [],
  activeConversationId: null,

  setAgentStatus: (status) => set({ agentStatus: status }),

  addMessage: (message) => set((state) => ({
    messages: [...state.messages, { ...message, id: Date.now() + Math.random() }]
  })),

  clearMessages: () => set({ messages: [] }),

  toggleDarkMode: () => set((state) => {
    const newMode = !state.darkMode
    localStorage.setItem('darkMode', String(newMode))
    return { darkMode: newMode }
  }),

  setApiEndpoint: (endpoint) => {
    localStorage.setItem('apiEndpoint', endpoint)
    set({ apiEndpoint: endpoint })
  },

  startNewConversation: () => {
    const id = Date.now()
    set((state) => ({
      conversations: [...state.conversations, { id, title: 'New Chat', messages: [] }],
      activeConversationId: id,
      messages: [],
    }))
  },

  saveCurrentConversation: () => {
    const { messages, activeConversationId, conversations } = get()
    if (!activeConversationId || messages.length === 0) return
    const title = messages[0]?.content?.substring(0, 40) || 'Chat'
    set({
      conversations: conversations.map(c =>
        c.id === activeConversationId
          ? { ...c, title, messages: [...messages] }
          : c
      )
    })
  },

  loadConversation: (id) => {
    const { conversations } = get()
    const conv = conversations.find(c => c.id === id)
    if (conv) {
      set({ activeConversationId: id, messages: [...conv.messages] })
    }
  },
}))

export default useStore
