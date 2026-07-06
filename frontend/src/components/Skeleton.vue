<script setup>
defineProps({
  blocks: { type: Number, default: 3 },
})
</script>

<template>
  <div class="skeleton" aria-busy="true">
    <div v-for="i in blocks" :key="i" class="skeleton-block"></div>
  </div>
</template>
