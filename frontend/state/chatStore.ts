import type { FilterSpec } from '../lib_api';

// Super simple in-memory state store no persistence, no complexity
// Just holds the chat messages and current filters during the session

let messages: any[] = [
  {
    role: 'assistant',
    content:
      'Hi! Describe what you need and I will recommend products. You can also attach a photo of an item you like.',
  },
];

let filters: FilterSpec = {}; // Active search filters

export function getMessages() {
  return messages; // Get the current chat history
}

export function setMessages(next: any[]) {
  messages = next; // Update chat history
}

export function getFilters(): FilterSpec {
  return filters; // Get current search filters
}

export function setFilters(next: FilterSpec) {
  filters = next; // Update search filters
}

export function resetChat() {
  // Reset everything back to initial state like a fresh page load
  messages = [
    {
      role: 'assistant',
      content:
        'Hi! Describe what you need and I will recommend products. You can also attach a photo of an item you like.',
    },
  ];
  filters = {} as FilterSpec; // Clear all filters too
}

