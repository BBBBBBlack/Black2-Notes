import time
from data import *
from models.model.transformer import Transformer
from util.bleu import idx_to_word, get_bleu

# 开始时间
start_time = time.time()
model = Transformer(src_pad_idx=src_pad_idx,
                    trg_pad_idx=trg_pad_idx,
                    trg_sos_idx=trg_sos_idx,
                    d_model=d_model,
                    enc_voc_size=enc_voc_size,
                    dec_voc_size=dec_voc_size,
                    max_len=max_len,
                    ffn_hidden=ffn_hidden,
                    n_head=n_heads,
                    n_layers=n_layers,
                    drop_prob=drop_prob,
                    device=device).to(device)
# 导入模型
model.load_state_dict(torch.load('.\\saved\\model-4.450539341339698.pt'))
model.eval()
# 初始的trg是一个开始符号(一个tensor)
# trg = torch.Tensor([[2]]).type_as(src.data).to(device)
for i, batch in enumerate(test_iter):
    src = batch.src
    real_trg = batch.trg
    trg = torch.full((batch_size, 1), trg_sos_idx, device=device)
    cache = None
    # while trg.size(-1) < max_len:
    #     output = model(src, trg, use_cache=False, cache=None)
    #     output_reshape = output.contiguous().view(-1, output.shape[-1])
    #     predict = torch.argmax(output, dim=2)
    #     trg = torch.cat((trg, predict[:, -1].unsqueeze(-1)), dim=1)
    #     # predict的最后一个元素是结束符号
    #     if (predict[:, -1] == trg_eos_idx).all().item():
    #         break

    while trg.size(-1) < max_len:
        output, cache = model(src, trg, use_cache=True, cache=cache)
        output_reshape = output.contiguous().view(-1, output.shape[-1])
        predict = torch.argmax(output, dim=2)
        trg = torch.cat((trg, predict[:, -1].unsqueeze(-1)), dim=1)
        # trg = predict
        # predict的最后一个元素是结束符号
        if (predict[:, -1] == trg_eos_idx).all().item():
            break

    # # 计算bleu
    # avg_bleu = []
    # for j in range(batch_size):
    #     output_words = idx_to_word(trg[j], loader.target.vocab)
    #     # output_words = idx_to_word(sentence[j], loader.target.vocab)
    #     real_words = idx_to_word(real_trg[j], loader.target.vocab)
    #     bleu = get_bleu(hypotheses=output_words.split(), reference=real_words.split())
    #     avg_bleu.append(bleu)
    # avg_bleu = sum(avg_bleu) / len(avg_bleu)
    # print(avg_bleu)
# 结束时间
end_time = time.time()
print('time :', end_time - start_time)