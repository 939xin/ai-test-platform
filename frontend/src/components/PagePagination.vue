<script setup>
/**
 * 列表页统一分页条。
 *
 * 只包了一层 el-pagination，为的是把 layout、每页条数选项和样式收在一处 ——
 * 6 个列表页各写一遍迟早会漂移（这个少了 sizes、那个加了 jumper）。
 *
 * 「共 N 条」不在这里显示：各列表页顶部 .card-tools 已经有了，重复显示两遍反而乱。
 *
 * hide-on-single-page：一页装得下就整条不渲染。否则 3 条数据的列表底下也会挂一条
 * 全禁用的分页栏（上一页 / 下一页都是灰的），纯噪音 —— 加了这个，条目少的页面
 * 看起来和没做分页时一模一样。代价是「每页条数」选择器在单页时也一起消失，
 * 但那种情况本来也没啥可翻的。
 *
 * 不走 v-model，只发一个 change 事件带上 { page, pageSize }：
 * 改每页条数时要连带把页码重置回 1，两件事必须一起生效。
 * 拆成两个 v-model 的话，父组件得自己保证这个先后顺序，容易漏。
 */
const props = defineProps({
  /** 当前页码，从 1 开始 */
  page: { type: Number, required: true },
  /** 每页条数 */
  pageSize: { type: Number, default: 20 },
  /** 筛选后的总条数（后端 Page.total），不是本页条数 */
  total: { type: Number, default: 0 },
})

const emit = defineEmits(['change'])

const PAGE_SIZES = [10, 20, 50, 100]

function onCurrentChange(value) {
  emit('change', { page: value, pageSize: props.pageSize })
}

function onSizeChange(value) {
  // 改每页条数一律回到第 1 页：留在原页码很可能已经越界，
  // 用户会看到一张空表还以为数据没了（分页最常见的坑）
  emit('change', { page: 1, pageSize: value })
}
</script>

<template>
  <div v-if="total > 0" class="pager">
    <el-pagination
      background
      hide-on-single-page
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="PAGE_SIZES"
      :total="total"
      layout="sizes, prev, pager, next, jumper"
      @current-change="onCurrentChange"
      @size-change="onSizeChange"
    />
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
