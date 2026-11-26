<template>
  <view class="page">
    <!-- 顶栏 -->
    <view class="header" :style="{ paddingTop: statusBarHeight + 'px' }">
      <text class="header-title">集群监控</text>
      <text class="header-sub">OPS Monitor</text>
    </view>

    <!-- 集群摘要统计 -->
    <view class="summary" v-if="servers.length > 0">
      <view class="summary-item">
        <text class="summary-num">{{ servers.length }}</text>
        <text class="summary-label">总节点</text>
      </view>
      <view class="summary-item">
        <text class="summary-num ok">{{ onlineCount }}</text>
        <text class="summary-label">正常</text>
      </view>
      <view class="summary-item">
        <text class="summary-num warn">{{ alertCount }}</text>
        <text class="summary-label">告警</text>
      </view>
    </view>

    <!-- 加载 / 空状态 -->
    <view v-if="loading && servers.length === 0" class="empty">
      <text class="empty-text">加载中...</text>
    </view>
    <view v-else-if="servers.length === 0" class="empty">
      <text class="empty-text" @click="fetchStatus">暂无数据, 点击重试</text>
    </view>

    <!-- 服务器卡片列表 -->
    <view class="card" v-for="(s, i) in servers" :key="i"
          @click="goDetail(s.ip)">
      <view class="card-head">
        <text class="card-name">{{ s.hostname || s.ip }}</text>
        <text class="card-ip">{{ s.ip }}</text>
      </view>

      <!-- CPU -->
      <view class="metric">
        <text class="metric-label">CPU</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.cpu > 80 }"
                :style="{ width: Math.min(s.cpu, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.cpu > 80 }">{{ s.cpu.toFixed(1) }}%</text>
      </view>

      <!-- 内存 -->
      <view class="metric">
        <text class="metric-label">内存</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.mem > 80 }"
                :style="{ width: Math.min(s.mem, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.mem > 80 }">{{ s.mem.toFixed(1) }}%</text>
      </view>

      <!-- 磁盘 -->
      <view class="metric">
        <text class="metric-label">磁盘</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.disk > 80 }"
                :style="{ width: Math.min(s.disk, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.disk > 80 }">{{ s.disk.toFixed(1) }}%</text>
      </view>

      <!-- 服务状态标签 -->
      <view class="svc-row">
        <text class="svc-label">服务:</text>
        <view class="svc-tags">
          <text v-for="svc in s.svcList" :key="svc.name"
                :class="svc.status === 'active' ? 'tag-ok' : 'tag-err'">
            {{ svc.name }}: {{ svc.status }}
          </text>
        </view>
      </view>

      <!-- 点击提示 -->
      <view class="card-arrow">
        <text class="arrow-text">查看详情 ></text>
      </view>
    </view>

    <!-- 底部安全区占位 -->
    <view style="height: 120rpx;"></view>
  </view>
</template>

<script>
import request from '../../utils/request.js'

export default {
  data() {
    return {
      statusBarHeight: 0,
      servers: [],
      loading: false
    }
  },
  computed: {
    // 正常节点: 所有服务都是 active
    onlineCount() {
      return this.servers.filter(s =>
        s.svcList.length > 0 && s.svcList.every(v => v.status === 'active')
      ).length
    },
    // 告警节点: 任意指标超 80% 或有非 active 服务
    alertCount() {
      return this.servers.filter(s =>
        s.cpu > 80 || s.mem > 80 || s.disk > 80 ||
        s.svcList.some(v => v.status !== 'active')
      ).length
    }
  },
  onLoad() {
    this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
  },
  onShow() {
    // 每次显示时检查登录态
    const token = uni.getStorageSync('ops_token')
    if (!token) {
      uni.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.fetchStatus()
  },
  onPullDownRefresh() {
    this.fetchStatus()
    setTimeout(() => uni.stopPullDownRefresh(), 1000)
  },
  methods: {
    // 解析服务状态字符串
    parseSvcPairs(svcStr) {
      if (!svcStr || svcStr === '-') return []
      return svcStr.split(',').map(s => {
        const parts = s.trim().split('=')
        return { name: parts[0] || '', status: parts[1] || 'unknown' }
      }).filter(s => s.name)
    },

    fetchStatus() {
      this.loading = true
      request({ url: '/api/status' }).then(res => {
        if (Array.isArray(res.data)) {
          this.servers = res.data.map(s => ({
            ...s,
            cpu:  Number(s.cpu)  || 0,
            mem:  Number(s.mem)  || 0,
            disk: Number(s.disk) || 0,
            svcList: this.parseSvcPairs(s.services)
          }))
        }
      }).catch(() => {}).finally(() => { this.loading = false })
    },

    goDetail(ip) {
      uni.navigateTo({ url: '/pages/detail/detail?ip=' + ip })
    }
  }
}
</script>

<style>
.page { background: #f0f2f5; min-height: 100vh; }

/* 顶栏 */
.header { background: #1f2937; padding: 24rpx 30rpx;
          display: flex; justify-content: space-between; align-items: center; }
.header-title { color: #fff; font-size: 34rpx; font-weight: 600; }
.header-sub { color: #64748b; font-size: 24rpx; }

/* 集群摘要 */
.summary { display: flex; justify-content: space-around; background: #fff;
           margin: 20rpx 24rpx 0; border-radius: 12rpx; padding: 24rpx 0;
           box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }
.summary-item { text-align: center; }
.summary-num { display: block; font-size: 40rpx; font-weight: 700; color: #1f2937; }
.summary-num.ok { color: #16a34a; }
.summary-num.warn { color: #dc2626; }
.summary-label { font-size: 22rpx; color: #9ca3af; }

/* 卡片 */
.card { background: #fff; margin: 20rpx 24rpx 0; border-radius: 16rpx;
        padding: 28rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }
.card-head { display: flex; justify-content: space-between; align-items: center;
             margin-bottom: 20rpx; }
.card-name { font-size: 32rpx; font-weight: 600; color: #1f2937; }
.card-ip   { font-size: 24rpx; color: #9ca3af; }

/* 指标行 */
.metric { display: flex; align-items: center; margin-bottom: 14rpx; }
.metric-label { width: 80rpx; font-size: 24rpx; color: #6b7280; }
.bar-bg { flex: 1; height: 20rpx; background: #e5e7eb; border-radius: 10rpx;
          overflow: hidden; margin: 0 16rpx; }
.bar-fill { height: 100%; background: #22c55e; border-radius: 10rpx;
            transition: width .3s; }
.bar-warn { background: #ef4444; }
.metric-val { width: 100rpx; text-align: right; font-size: 24rpx; color: #374151;
              font-weight: 600; }
.val-warn { color: #ef4444; }

/* 服务状态 */
.svc-row { display: flex; align-items: center; margin-top: 10rpx; font-size: 24rpx; }
.svc-label { color: #6b7280; margin-right: 8rpx; flex-shrink: 0; }
.svc-tags { display: flex; flex-wrap: wrap; gap: 8rpx; }
.tag-ok  { background: #dcfce7; color: #16a34a; padding: 4rpx 14rpx;
           border-radius: 6rpx; font-size: 22rpx; }
.tag-err { background: #fee2e2; color: #dc2626; padding: 4rpx 14rpx;
           border-radius: 6rpx; font-size: 22rpx; }

/* 卡片底部箭头 */
.card-arrow { text-align: right; margin-top: 16rpx; }
.arrow-text { font-size: 22rpx; color: #9ca3af; }

/* 空状态 */
.empty { display: flex; justify-content: center; align-items: center; height: 400rpx; }
.empty-text { font-size: 28rpx; color: #9ca3af; }
</style>
