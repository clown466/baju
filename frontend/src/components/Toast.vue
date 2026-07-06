<script setup>
import { useToast } from '../composables/useToast'

const { toasts, remove } = useToast()
</script>

<template>
  <div class="toast-container">
    <div v-for="t in toasts" :key="t.id"
         :class="['toast', t.type]" @click="remove(t.id)">
      <span class="toast-icon">{{ t.type === 'success' ? '✓' : '✕' }}</span>
      {{ t.message }}
    </div>
  </div>
</template>
