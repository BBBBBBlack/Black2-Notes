[源代码](https://github.com/Rtoax/linux-5.10.13/blob/master/arch/x86/kernel/alternative.c#L935)
```c
/**
 *  修改 addr 处 的指令为 opcode
 */
static void *__text_poke(void *addr, const void *opcode, size_t len)
{
    /**
     *  是否在页的边界上
     *
     *       page1         page2
     *  |--------------+-------------|
     *              ^^^^^^^
     */
	bool cross_page_boundary = offset_in_page(addr) + len > PAGE_SIZE;
	struct page *pages[2] = {NULL};
	temp_mm_state_t prev;
	unsigned long flags;
	pte_t pte, *ptep;
	spinlock_t *ptl;
	pgprot_t pgprot;

	/*
	 * While boot memory allocator is running we cannot use struct pages as
	 * they are not yet initialized. There is no way to recover.
	 */
	BUG_ON(!after_bootmem);

    /**
     *  如果不是内核代码段 _stext ~ _etext
     */
	if (!core_kernel_text((unsigned long)addr)) {
        /**
         *  不是内核代码段，加上通过前面注册时候的判断，这里肯定是 module模块内部的代码
         *  所以可以使用 vmalloc 的API 查找对应的 page
         */
		pages[0] = vmalloc_to_page(addr);
        /**
         *
         *  是否在页的边界上
         *
         *       page1         page2
         *  |--------------+-------------|
         *              ^^^^^^^
         */
		if (cross_page_boundary)
			pages[1] = vmalloc_to_page(addr + PAGE_SIZE);
    }
    /**
     *  是内核 代码段地址
     */
    else {

        /**
         *
         */
		pages[0] = virt_to_page(addr);
		WARN_ON(!PageReserved(pages[0]));
		if (cross_page_boundary)
			pages[1] = virt_to_page(addr + PAGE_SIZE);
	}
	/*
	 * If something went wrong, crash and burn since recovery paths are not
	 * implemented.
	 */
	BUG_ON(!pages[0] || (cross_page_boundary && !pages[1]));

	/*
	 * Map the page without the global bit, as TLB flushing is done with
	 * flush_tlb_mm_range(), which is intended for non-global PTEs.
	 *
	 * 属性
	 */
	pgprot = __pgprot(pgprot_val(PAGE_KERNEL) & ~_PAGE_GLOBAL);

	/*
	 * The lock is not really needed, but this allows to avoid open-coding.
	 */
	ptep = get_locked_pte(poking_mm, poking_addr, &ptl);

	/*
	 * This must not fail; preallocated in poking_init().
	 */
	VM_BUG_ON(!ptep);

	local_irq_save(flags);

	/**
	 *
	 */
	pte = mk_pte(pages[0], pgprot);
	set_pte_at(poking_mm, poking_addr, ptep, pte);

	if (cross_page_boundary) {
		pte = mk_pte(pages[1], pgprot);
		set_pte_at(poking_mm, poking_addr + PAGE_SIZE, ptep + 1, pte);
	}

	/*
	 * Loading the temporary mm behaves as a compiler barrier, which
	 * guarantees that the PTE will be set at the time memcpy() is done.
	 */
	prev = use_temporary_mm(poking_mm);

	kasan_disable_current();

    /**
     *  代码注入
	 * 也就是 替换代码，在用户太可以使用 pwrite() 完成
     */
	memcpy((u8 *)poking_addr + offset_in_page(addr), opcode, len);

	kasan_enable_current();

	/*
	 * Ensure that the PTE is only cleared after the instructions of memcpy
	 * were issued by using a compiler barrier.
	 */
	barrier();

	pte_clear(poking_mm, poking_addr, ptep);

	if (cross_page_boundary)
		pte_clear(poking_mm, poking_addr + PAGE_SIZE, ptep + 1);

	/*
	 * Loading the previous page-table hierarchy requires a serializing
	 * instruction that already allows the core to see the updated version.
	 * Xen-PV is assumed to serialize execution in a similar manner.
	 */
	unuse_temporary_mm(prev);

	/*
	 * Flushing the TLB might involve IPIs, which would require enabled
	 * IRQs, but not if the mm is not used, as it is in this point.
	 *
	 * 刷新 TLB 指令缓存
	 */
	flush_tlb_mm_range(poking_mm, poking_addr, poking_addr +
            			   (cross_page_boundary ? 2 : 1) * PAGE_SIZE,
            			   PAGE_SHIFT, false);

	/*
	 * If the text does not match what we just wrote then something is
	 * fundamentally screwy; there's nothing we can really do about that.
	 *
	 *
	 */
	BUG_ON(memcmp(addr, opcode, len));

	local_irq_restore(flags);
	pte_unmap_unlock(ptep, ptl);
	return addr;
}

```

