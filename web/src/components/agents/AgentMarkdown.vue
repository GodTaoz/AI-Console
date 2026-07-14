<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'

const props = defineProps<{ content: string }>()

const markdown = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  typographer: false,
})

const defaultValidateLink = markdown.validateLink.bind(markdown)
const unsafeProtocol = /^(?:javascript:|vbscript:|data:|file:)/i
markdown.validateLink = (url) => {
  let decoded = url
  try { decoded = decodeURIComponent(url) } catch { /* Invalid escapes remain subject to the default validator. */ }
  return defaultValidateLink(url) && !unsafeProtocol.test(decoded.trim())
}
const defaultLinkOpen = markdown.renderer.rules.link_open
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen ? defaultLinkOpen(tokens, index, options, env, self) : self.renderToken(tokens, index, options)
}

const rendered = computed(() => markdown.render(props.content || ''))
</script>

<template>
  <div class="agent-markdown" v-html="rendered" />
</template>
