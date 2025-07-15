查询词右侧的值都被屏蔽，使用mask将其设为无穷小

![img](..\assets\1uyuyOW1VBqmF5Gtv225XHQ.gif)

```python
		q, k, v = self.w_q(q), self.w_k(k), self.w_v(v)

        # 2. split tensor by number of heads [batch_size, head, length, d_tensor]
        q, k, v = self.split(q), self.split(k), self.split(v)

        if cache is not None:
            past_key, past_value = cache
            k = torch.cat((past_key, k), dim=2)
            v = torch.cat((past_value, v), dim=2)
        # 3. do scale dot product to compute similarity
        out, attention = self.attention(q, k, v, mask=mask)
        # 4. concat and pass to linear layer
        out = self.concat(out)
        out = self.w_concat(out)
        if use_cache:
            return out, (k, v)
        else:
            return out
```

每个block都要存储cache

```python
        if cache is not None:
            cache_dict = cache
        else:
            cache_dict = {}
        for i, layer in enumerate(self.layers):
            if use_cache:
                trg, cache_dict[i] = layer(trg, enc_src, trg_mask, src_mask, use_cache, cache_dict.get(i))
            else:
                trg = layer(trg, enc_src, trg_mask, src_mask, use_cache, cache)
```

