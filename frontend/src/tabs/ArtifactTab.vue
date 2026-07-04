<script>
export default { name: 'ArtifactTab' }
</script>
<script setup>
defineProps({
  pid: { type: String, required: true },
  kind: { type: String, required: true },
  generateLabel: { type: String, required: true },
})
</script>
<template>
  <div>产物页签（待实现）</div>
</template>
