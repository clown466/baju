<script setup>
import { computed } from 'vue'

const props = defineProps({
  done: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  indeterminate: { type: Boolean, default: false },
})

const pct = computed(() => {
  if (!props.total) return '0%'
  return `${Math.round((props.done / props.total) * 10000) / 100}%`
})
</script>

<template>
  <div :class="['progress-bar', { indeterminate }]">
    <div class="progress-track">
      <div class="progress-fill" :style="indeterminate ? {} : { width: pct }"></div>
    </div>
    <span v-if="!indeterminate" class="progress-text">{{ done }}/{{ total }}</span>
  </div>
</template>
