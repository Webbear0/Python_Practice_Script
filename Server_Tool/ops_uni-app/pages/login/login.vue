<template>
  <view class="page">
    <!-- 顶部标题区 -->
    <view class="logo-area" :style="{ paddingTop: statusBarHeight + 'px' }">
      <text class="logo-icon">OPS</text>
      <text class="logo-title">掌上运维</text>
      <text class="logo-desc">集群监控与远程管理平台</text>
    </view>

    <!-- 登录表单 -->
    <view class="form-card">
      <view class="form-item">
        <text class="form-label">网关地址</text>
        <input class="form-input" v-model="gateway"
               placeholder="如 http://172.16.10.252" />
      </view>
      <view class="form-item">
        <text class="form-label">管理员账号</text>
        <input class="form-input" v-model="username" placeholder="请输入账号" />
      </view>
      <view class="form-item">
        <text class="form-label">登录密码</text>
        <input class="form-input" v-model="password" type="password"
               placeholder="请输入密码" />
      </view>
      <view class="login-btn" :class="{ 'btn-disabled': logging }" @click="doLogin">
        <text class="login-btn-text">{{ logging ? '登录中...' : '登 录' }}</text>
      </view>
    </view>

    <text class="footer">OPS Monitor | Nginx + Gunicorn + Flask</text>
  </view>
</template>

<script>
export default {
  data() {
    return {
      statusBarHeight: 0,
      gateway: '',
      username: '',
      password: '',
      logging: false
    }
  },
  onLoad() {
    this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
    // 回填已保存的网关地址
    const saved = uni.getStorageSync('ops_gateway')
    if (saved) this.gateway = saved
  },
  methods: {
    doLogin() {
      if (this.logging) return
      let gw = this.gateway.trim()
      const user = this.username.trim()
      const pass = this.password.trim()
      if (!gw) return uni.showToast({ title: '请输入网关地址', icon: 'none' })
      if (!user || !pass) return uni.showToast({ title: '请输入账号和密码', icon: 'none' })

      // 自动补全协议头, 去除末尾斜杠
      if (!/^https?:\/\//.test(gw)) gw = 'http://' + gw
      gw = gw.replace(/\/+$/, '')

      this.logging = true
      uni.request({
        url: gw + '/api/login',
        method: 'POST',
        header: { 'Content-Type': 'application/json' },
        data: { username: user, password: pass },
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.success) {
            // 持久化保存网关地址、Token、用户名
            uni.setStorageSync('ops_gateway', gw)
            uni.setStorageSync('ops_token', res.data.token)
            uni.setStorageSync('ops_username', res.data.username)
            uni.showToast({ title: '登录成功', icon: 'success' })
            setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 500)
          } else {
            const msg = (res.data && res.data.message) || '登录失败'
            uni.showToast({ title: msg, icon: 'none' })
          }
        },
        fail: () => {
          uni.showToast({ title: '连接失败, 请检查网关地址', icon: 'none', duration: 2000 })
        },
        complete: () => { this.logging = false }
      })
    }
  }
}
</script>

<style>
.page { background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
        min-height: 100vh; display: flex; flex-direction: column; align-items: center; }

/* 顶部标题 */
.logo-area { text-align: center; padding: 80rpx 0 50rpx; }
.logo-icon { display: block; font-size: 48rpx; font-weight: 800;
             color: #60a5fa; letter-spacing: 6rpx; margin-bottom: 12rpx; }
.logo-title { display: block; font-size: 40rpx; font-weight: 600;
              color: #f1f5f9; margin-bottom: 10rpx; }
.logo-desc { display: block; font-size: 24rpx; color: #64748b; }

/* 表单卡片 */
.form-card { background: #1e293b; border: 1px solid #334155; border-radius: 16rpx;
             padding: 40rpx 36rpx; margin: 20rpx 40rpx; width: 620rpx; }
.form-item { margin-bottom: 28rpx; }
.form-label { display: block; font-size: 24rpx; color: #94a3b8; margin-bottom: 10rpx; }
.form-input { background: #0f172a; border: 1px solid #334155; border-radius: 8rpx;
              padding: 18rpx 20rpx; font-size: 28rpx; color: #e2e8f0; width: 100%; }

/* 登录按钮 */
.login-btn { background: #3b82f6; border-radius: 10rpx; padding: 22rpx 0;
             text-align: center; margin-top: 10rpx; }
.login-btn-text { color: #fff; font-size: 30rpx; font-weight: 600; }
.btn-disabled { opacity: 0.5; }

/* 底部 */
.footer { position: fixed; bottom: 40rpx; font-size: 22rpx; color: #475569; }
</style>
