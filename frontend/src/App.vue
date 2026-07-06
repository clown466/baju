<script setup>
import ConfirmDialog from './components/ConfirmDialog.vue'
import Toast from './components/Toast.vue'
</script>

<template>
  <header class="topbar">
    <router-link class="brand" to="/">🎬 短剧扒剧与仿写</router-link>
    <router-link class="topbar-settings" to="/settings">⚙ 模型设置</router-link>
  </header>
  <main>
    <router-view v-slot="{ Component }">
      <Transition name="fade" mode="out-in">
        <component :is="Component" />
      </Transition>
    </router-view>
  </main>
  <Toast />
  <ConfirmDialog />
</template>
