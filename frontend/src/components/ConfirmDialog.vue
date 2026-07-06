<script setup>
import { useConfirm } from '../composables/useConfirm'

const { state, settle } = useConfirm()
</script>

<template>
  <div v-if="state.visible" class="confirm-mask">
    <div class="confirm-card">
      <p class="confirm-message">{{ state.message }}</p>
      <div class="confirm-actions">
        <button type="button" class="danger" @click="settle(true)">确定</button>
        <button type="button" @click="settle(false)">取消</button>
      </div>
    </div>
  </div>
</template>
