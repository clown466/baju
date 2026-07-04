<script setup>
import { ref, watch } from 'vue'
import MarkdownView from './MarkdownView.vue'

const props = defineProps({
  content: { type: String, default: '' },
  markdown: { type: Boolean, default: true },
})
const emit = defineEmits(['save'])

const editing = ref(false)
const draft = ref(props.content)
watch(() => props.content, (v) => {
  if (!editing.value) draft.value = v
})

function startEdit() {
  draft.value = props.content
  editing.value = true
}
function save() {
  emit('save', draft.value)
  editing.value = false
}
</script>

<template>
  <div class="editor-pane">
    <div class="toolbar">
      <button v-if="!editing" @click="startEdit">编辑</button>
      <template v-else>
        <button @click="save">保存</button>
        <button @click="editing = false">取消编辑</button>
      </template>
    </div>
    <textarea v-if="editing" v-model="draft" rows="24"></textarea>
    <MarkdownView v-else-if="markdown" :content="content" />
    <pre v-else class="plain">{{ content }}</pre>
  </div>
</template>
