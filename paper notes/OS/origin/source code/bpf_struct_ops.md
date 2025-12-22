### userspace

#### 应用程序

```c++
SEC("struct_ops/dctcp_init")
void BPF_PROG(dctcp_init, struct sock *sk)
{
    const struct tcp_sock *tp = tcp_sk(sk);
    struct dctcp *ca = inet_csk_ca(sk);
    int *stg;

    ca->prior_rcv_nxt = tp->rcv_nxt;
    ca->dctcp_alpha = min(dctcp_alpha_on_init, DCTCP_MAX_ALPHA);
    ca->loss_cwnd = 0;
    ca->ce_state = 0;

    stg = bpf_sk_storage_get(&sk_stg_map, (void *)tp, NULL, 0);
    if (stg) {
        stg_result = *stg;
        bpf_sk_storage_delete(&sk_stg_map, (void *)tp);
    }
    dctcp_reset(tp, ca);
}

SEC("struct_ops/dctcp_cwnd_undo")
__u32 BPF_PROG(dctcp_cwnd_undo, struct sock *sk)
{
    const struct dctcp *ca = inet_csk_ca(sk);

    return max(tcp_sk(sk)->snd_cwnd, ca->loss_cwnd);
}

// SEC(".struct_ops") —— 对应BPF_MAP_TYPE_STRUCT_OPS类型的MAP
SEC(".struct_ops")
struct tcp_congestion_ops dctcp_nouse = {
    .init       = (void *)dctcp_init,
    .set_state  = (void *)dctcp_state,
    .flags      = TCP_CONG_NEEDS_ECN,
    .name       = "bpf_dctcp_nouse",
};

SEC(".struct_ops")
struct tcp_congestion_ops dctcp = {
    .init       = (void *)dctcp_init,
    .in_ack_event   = (void *)dctcp_update_alpha,
    .cwnd_event = (void *)dctcp_cwnd_event,
    .ssthresh   = (void *)dctcp_ssthresh,
    .cong_avoid = (void *)dctcp_cong_avoid,
    .undo_cwnd  = (void *)dctcp_cwnd_undo,
    .set_state  = (void *)dctcp_state,
    .flags      = TCP_CONG_NEEDS_ECN,
    .name       = "bpf_dctcp",
};
```

#### libbpf

```c++
struct bpf_struct_ops {
    /* 用户态的bpf prog信息（在程序中自定义的BPF函数的指针） */
	struct bpf_program **progs;
	__u32 *kern_func_off;
	/* e.g. struct tcp_congestion_ops in bpf_prog's btf format */
	void *data;
	/* e.g. struct bpf_struct_ops_tcp_congestion_ops in
	 *      btf_vmlinux's format.
	 * struct bpf_struct_ops_tcp_congestion_ops {
	 *	[... some other kernel fields ...]
	 *	struct tcp_congestion_ops data;
	 * }
	 * kern_vdata-size == sizeof(struct bpf_struct_ops_tcp_congestion_ops)
	 * bpf_map__init_kern_struct_ops() will populate the "kern_vdata"
	 * from "data".
	 */
	/* 准备发给内核的最终二进制数据（progs + data），会通过bpf_map_update_elem系统调用载入内核 */
	void *kern_vdata;
	__u32 type_id;
};
```

**open：**解析 ELF，建立关联

* 创建 BPF_MAP_TYPE_STRUCT_OPS bpf_map 对象，初始化其内部管理结构 struct bpf_struct_ops
* Libbpf 解析 `.struct_ops` section 中的重定位信息或通过名字匹配，找到结构体函数指针字段（如 `.init`）对应的 BPF Program 对象（`struct bpf_program`）
* 将这些 BPF Program 对象的引用存放在 bpf_struct_ops 内部的 `progs` 数组中

```
bpf_object__open
  -> bpf_object__init_maps
      -> bpf_object__init_struct_ops
          -> bpf_map__init_struct_ops (解析 BTF，初始化内部结构，建立 prog 关联)
```

**load：**加载 BPF 程序，创建 Map

* 将 BPF Program 载入内核
* 创建 bpf_struct_ops 的 kern_vdata，将 progs（ BPF Program 载入内核返回的内核句柄）、data 填入
* 调用 BPF_MAP_CREATE 创建空 bpf_map

```
bpf_object__load
  -> bpf_object__prepare (处理重定位)
  -> bpf_object__load_progs (加载程序，拿到 FD)
  -> bpf_object__init_kern_struct_ops_maps (遍历所有 struct_ops map)
      -> bpf_map__init_kern_struct_ops (构建 kern_vdata，填入 FD)
  -> bpf_object__create_maps (真正调用 bpf_map_create / update 发给内核)
```

**attach：**激活并管理生命周期

调用 bpf_map__attach_struct_ops，传入**load**阶段创建的 bpf_map 指针

```c++
struct bpf_link *bpf_map__attach_struct_ops(const struct bpf_map *map)
{
	struct bpf_link_struct_ops *link;
	__u32 zero = 0;
	int err, fd;

	if (!bpf_map__is_struct_ops(map)) {
		pr_warn("map '%s': can't attach non-struct_ops map\n", map->name);
		return libbpf_err_ptr(-EINVAL);
	}

	if (map->fd < 0) {
		pr_warn("map '%s': can't attach BPF map without FD (was it created?)\n", map->name);
		return libbpf_err_ptr(-EINVAL);
	}

	link = calloc(1, sizeof(*link));
	if (!link)
		return libbpf_err_ptr(-EINVAL);

	/* 用vdata里的数据来更新map，vdata在load期间完成了数据的初始化 */
	err = bpf_map_update_elem(map->fd, &zero, map->st_ops->kern_vdata, 0);
	/* It can be EBUSY if the map has been used to create or
	 * update a link before.  We don't allow updating the value of
	 * a struct_ops once it is set.  That ensures that the value
	 * never changed.  So, it is safe to skip EBUSY.
	 */
	if (err && (!(map->def.map_flags & BPF_F_LINK) || err != -EBUSY)) {
		free(link);
		return libbpf_err_ptr(err);
	}

	link->link.detach = bpf_link__detach_struct_ops;

	if (!(map->def.map_flags & BPF_F_LINK)) {
		/* w/o a real link */
		link->link.fd = map->fd;
		link->map_fd = -1;
		return &link->link;
	}

	/* 挂载操作：将map进行attach */
	fd = bpf_link_create(map->fd, 0, BPF_STRUCT_OPS, NULL);
	if (fd < 0) {
		free(link);
		return libbpf_err_ptr(fd);
	}

	link->link.fd = fd;
	link->map_fd = map->fd;

	return &link->link;
}
```

### kernel

**bpf_struct_ops**

```c++
#define BPF_STRUCT_OPS_MAX_NR_MEMBERS 64
/**
 * struct bpf_struct_ops - A structure of callbacks allowing a subsystem to
 *			   define a BPF_MAP_TYPE_STRUCT_OPS map type composed
 *			   of BPF_PROG_TYPE_STRUCT_OPS progs.
 * @verifier_ops: A structure of callbacks that are invoked by the verifier
 *		  when determining whether the struct_ops progs in the
 *		  struct_ops map are valid.
 * @init: A callback that is invoked a single time, and before any other
 *	  callback, to initialize the structure. A nonzero return value means
 *	  the subsystem could not be initialized.
 * @check_member: When defined, a callback invoked by the verifier to allow
 *		  the subsystem to determine if an entry in the struct_ops map
 *		  is valid. A nonzero return value means that the map is
 *		  invalid and should be rejected by the verifier.
 * @init_member: A callback that is invoked for each member of the struct_ops
 *		 map to allow the subsystem to initialize the member. A nonzero
 *		 value means the member could not be initialized. This callback
 *		 is exclusive with the @type, @type_id, @value_type, and
 *		 @value_id fields.
 * @reg: A callback that is invoked when the struct_ops map has been
 *	 initialized and is being attached to. Zero means the struct_ops map
 *	 has been successfully registered and is live. A nonzero return value
 *	 means the struct_ops map could not be registered.
 * @unreg: A callback that is invoked when the struct_ops map should be
 *	   unregistered.
 * @update: A callback that is invoked when the live struct_ops map is being
 *	    updated to contain new values. This callback is only invoked when
 *	    the struct_ops map is loaded with BPF_F_LINK. If not defined, the
 *	    it is assumed that the struct_ops map cannot be updated.
 * @validate: A callback that is invoked after all of the members have been
 *	      initialized. This callback should perform static checks on the
 *	      map, meaning that it should either fail or succeed
 *	      deterministically. A struct_ops map that has been validated may
 *	      not necessarily succeed in being registered if the call to @reg
 *	      fails. For example, a valid struct_ops map may be loaded, but
 *	      then fail to be registered due to there being another active
 *	      struct_ops map on the system in the subsystem already. For this
 *	      reason, if this callback is not defined, the check is skipped as
 *	      the struct_ops map will have final verification performed in
 *	      @reg.
 * @type: BTF type.
 * @value_type: Value type.
 * @name: The name of the struct bpf_struct_ops object.
 * @func_models: Func models
 * @type_id: BTF type id.
 * @value_id: BTF value id.
 */
struct bpf_struct_ops {
	const struct bpf_verifier_ops *verifier_ops;
	int (*init)(struct btf *btf);
	int (*check_member)(const struct btf_type *t,
			    const struct btf_member *member,
			    const struct bpf_prog *prog);
	int (*init_member)(const struct btf_type *t,
			   const struct btf_member *member,
			   void *kdata, const void *udata);
	int (*reg)(void *kdata, void *more_data);
	void (*unreg)(void *kdata, void *more_data);
	int (*update)(void *kdata, void *old_kdata);
	int (*validate)(void *kdata);
	const struct btf_type *type;
	const struct btf_type *value_type;
	const char *name;
	struct btf_func_model func_models[BPF_STRUCT_OPS_MAX_NR_MEMBERS];
	u32 type_id;
	u32 value_id;
};
```



```c++
static struct bpf_struct_ops bpf_tcp_congestion_ops = {
	.verifier_ops = &bpf_tcp_ca_verifier_ops,
	.reg = bpf_tcp_ca_reg,
	.unreg = bpf_tcp_ca_unreg,
	.update = bpf_tcp_ca_update,
	.init_member = bpf_tcp_ca_init_member,
	.init = bpf_tcp_ca_init,
	.validate = bpf_tcp_ca_validate,
	.name = "tcp_congestion_ops",
	.cfi_stubs = &__bpf_ops_tcp_congestion_ops,
	.owner = THIS_MODULE,
};

static int __init bpf_tcp_ca_kfunc_init(void)
{
	int ret;

	/* 先注册我们给tcp_ca新增的那些kfunc函数，是按照BPF_PROG_TYPE_STRUCT_OPS
	 * 来注册的。然后再注册bpf_tcp_congestion_ops。
	 */
	ret = register_btf_kfunc_id_set(BPF_PROG_TYPE_STRUCT_OPS, &bpf_tcp_ca_kfunc_set);
	/* 这里会把这个bpf_tcp_congestion_ops结构体注册到btf->struct_ops_tab.ops
	 * 数组中的，后续也是根据"tcp_congestion_ops"这个名字来查找的。
	 */
	ret = ret ?: register_bpf_struct_ops(&bpf_tcp_congestion_ops, tcp_congestion_ops);

	return ret;
}
```

用户态在**attach**阶段：

```c++
// 用户态调用
bpf_map_update_elem(map_fd, &key, kern_vdata, flags);

// 内核处理路径
sys_bpf(BPF_MAP_UPDATE_ELEM)
  → map_update_elem()
    → bpf_struct_ops_map_update_elem()  // ← struct_ops 特有的 update 函数
```
内核态接受用户态传入的kern_vdata

```c++
/*
 * map: 用户态libbpf attach 阶段 create 的 map，包含内核态的 bpf_tcp_congestion_ops
 * 		(在 bpf_map__create 时通过系统调用，根据 BTF type_id 查找内核注册的struct_ops，从而找到
 * 		bpf_tcp_congestion_ops，而所有的struct_ops在内核启动时通过register_bpf_struct_ops注册)
 * 		map的结构：
        st_map (bpf_struct_ops_map 实例)
        ├─ map (struct bpf_map)
        ├─ st_ops → 指向全局的 bpf_tcp_congestion_ops
        ├─ links[64]
        ├─ image → [trampoline 代码页]
        │
        ├─ uvalue → 指向单独分配的内存:
        │           ┌─────────────────────────────┐
        │           │ refcnt, state               │
        │           │ data: [用户传来的原始数据]  │ ← udata 指向这里
        │           └─────────────────────────────┘
        │
        └─ kvalue (嵌入在 st_map 中!):
                    ┌─────────────────────────────┐
                    │ refcnt, state               │
                    │ data: [转换后的内核数据]    │ ← kdata 指向这里
                    └─────────────────────────────┘
                            ↑
                            └─ 包含 bpf_prog 指针/trampoline 地址
 * value: 用户态构建的 kern_vdata
 */
static long bpf_struct_ops_map_update_elem(struct bpf_map *map, void *key,
					   void *value, u64 flags)
{
	struct bpf_struct_ops_map *st_map = (struct bpf_struct_ops_map *)map;
	const struct bpf_struct_ops *st_ops = st_map->st_ops;
	struct bpf_struct_ops_value *uvalue, *kvalue;
	const struct btf_member *member;
	const struct btf_type *t = st_ops->type;
	struct bpf_tramp_links *tlinks;
	void *udata, *kdata;
	int prog_fd, err;
	void *image, *image_end;
	u32 i;

	if (flags)
		return -EINVAL;

	if (*(u32 *)key != 0)
		return -E2BIG;

	err = check_zero_holes(st_ops->value_type, value);
	if (err)
		return err;

	uvalue = value;
	err = check_zero_holes(t, uvalue->data);
	if (err)
		return err;

	if (uvalue->state || refcount_read(&uvalue->refcnt))
		return -EINVAL;

	tlinks = kcalloc(BPF_TRAMP_MAX, sizeof(*tlinks), GFP_KERNEL);
	if (!tlinks)
		return -ENOMEM;

	uvalue = (struct bpf_struct_ops_value *)st_map->uvalue;
	kvalue = (struct bpf_struct_ops_value *)&st_map->kvalue;

	mutex_lock(&st_map->lock);

	if (kvalue->state != BPF_STRUCT_OPS_STATE_INIT) {
		err = -EBUSY;
		goto unlock;
	}
	// 将 kern_vdata 拷贝到 map 内部的 uvalue 存储空间
	memcpy(uvalue, value, map->value_size);

	udata = &uvalue->data;
	kdata = &kvalue->data;
	image = st_map->image;
	image_end = st_map->image + PAGE_SIZE;

	for_each_member(i, t, member) {
		const struct btf_type *mtype, *ptype;
		struct bpf_prog *prog;
		struct bpf_tramp_link *link;
		u32 moff;

		moff = __btf_member_bit_offset(t, member) / 8;
		ptype = btf_type_resolve_ptr(btf_vmlinux, member->type, NULL);
		if (ptype == module_type) {
			if (*(void **)(udata + moff))
				goto reset_unlock;
			*(void **)(kdata + moff) = BPF_MODULE_OWNER;
			continue;
		}
		
		err = st_ops->init_member(t, member, kdata, udata);
		if (err < 0)
			goto reset_unlock;

		/* The ->init_member() has handled this member */
		if (err > 0)
			continue;

		/* If st_ops->init_member does not handle it,
		 * we will only handle func ptrs and zero-ed members
		 * here.  Reject everything else.
		 */

		/* All non func ptr member must be 0 */
		if (!ptype || !btf_type_is_func_proto(ptype)) {
			u32 msize;

			mtype = btf_type_by_id(btf_vmlinux, member->type);
			mtype = btf_resolve_size(btf_vmlinux, mtype, &msize);
			if (IS_ERR(mtype)) {
				err = PTR_ERR(mtype);
				goto reset_unlock;
			}

			if (memchr_inv(udata + moff, 0, msize)) {
				err = -EINVAL;
				goto reset_unlock;
			}

			continue;
		}
		
		prog_fd = (int)(*(unsigned long *)(udata + moff));
		/* Similar check as the attr->attach_prog_fd */
		if (!prog_fd)
			continue;
		// 将 kern_vdata 的 BPF 程序内核句柄 FD 转换为 bpf_prog 指针
		prog = bpf_prog_get(prog_fd);
		if (IS_ERR(prog)) {
			err = PTR_ERR(prog);
			goto reset_unlock;
		}

		if (prog->type != BPF_PROG_TYPE_STRUCT_OPS ||
		    prog->aux->attach_btf_id != st_ops->type_id ||
		    prog->expected_attach_type != i) {
			bpf_prog_put(prog);
			err = -EINVAL;
			goto reset_unlock;
		}

		link = kzalloc(sizeof(*link), GFP_USER);
		if (!link) {
			bpf_prog_put(prog);
			err = -ENOMEM;
			goto reset_unlock;
		}
		bpf_link_init(&link->link, BPF_LINK_TYPE_STRUCT_OPS,
			      &bpf_struct_ops_link_lops, prog);
		st_map->links[i] = &link->link;
		// 生成 trampoline 代码（内核函数指针到 BPF 程序的调用桥梁）
		err = bpf_struct_ops_prepare_trampoline(tlinks, link,
							&st_ops->func_models[i],
							image, image_end);
		if (err < 0)
			goto reset_unlock;
		// 将 trampoline 地址写入 kdata
		*(void **)(kdata + moff) = image;
		image += err;

		/* put prog_id to udata */
        // 更新 udata,记录 prog_id (用于用户态查询)
		*(unsigned long *)(udata + moff) = prog->aux->id;
	}

	if (st_map->map.map_flags & BPF_F_LINK) {
		err = 0;
		if (st_ops->validate) {
			err = st_ops->validate(kdata);
			if (err)
				goto reset_unlock;
		}
		set_memory_rox((long)st_map->image, 1);
		/* Let bpf_link handle registration & unregistration.
		 *
		 * Pair with smp_load_acquire() during lookup_elem().
		 */
		smp_store_release(&kvalue->state, BPF_STRUCT_OPS_STATE_READY);
		goto unlock;
	}

	set_memory_rox((long)st_map->image, 1);
    // reg回调，bpf_tcp_congestion_ops自定义的reg调用tcp_register_congestion_control
    // 将kdata放入全局链表
	err = st_ops->reg(kdata, NULL);
	if (likely(!err)) {
		/* This refcnt increment on the map here after
		 * 'st_ops->reg()' is secure since the state of the
		 * map must be set to INIT at this moment, and thus
		 * bpf_struct_ops_map_delete_elem() can't unregister
		 * or transition it to TOBEFREE concurrently.
		 */
		bpf_map_inc(map);
		/* Pair with smp_load_acquire() during lookup_elem().
		 * It ensures the above udata updates (e.g. prog->aux->id)
		 * can be seen once BPF_STRUCT_OPS_STATE_INUSE is set.
		 */
		smp_store_release(&kvalue->state, BPF_STRUCT_OPS_STATE_INUSE);
		goto unlock;
	}

	/* Error during st_ops->reg(). Can happen if this struct_ops needs to be
	 * verified as a whole, after all init_member() calls. Can also happen if
	 * there was a race in registering the struct_ops (under the same name) to
	 * a sub-system through different struct_ops's maps.
	 */
	set_memory_nx((long)st_map->image, 1);
	set_memory_rw((long)st_map->image, 1);

reset_unlock:
	bpf_struct_ops_map_put_progs(st_map);
	memset(uvalue, 0, map->value_size);
	memset(kvalue, 0, map->value_size);
unlock:
	kfree(tlinks);
	mutex_unlock(&st_map->lock);
	return err;
}
```

