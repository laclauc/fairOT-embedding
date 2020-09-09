import matplotlib.pyplot as plt
"""
# PolBlogs
DI = [0.1103742, 0.05473, 0.03620, 0.02256, 0.017624, 0.01624, 0.0084, 0.0131863, 0.0068]
Acc = [0.74351, 0.7349, 0.7291, 0.73493,0.78176,0.78119, 0.78424,  0.78300, 0.77556]
AUC = [0.801722, 0.8084, 0.8052, 0.7992, 0.8365,  0.8422, 0.83255,  0.8367, 0.83144]
dens = [0.07236,  0.12171, 0.1469, 0.1715, 0.2209, 0.27146, 0.3543266, 0.3958, 0.42073]

# Density and DI on the original graph
dens_original = 0.0224
DI_original = 0.0002

x = range(1, 10)

plt.plot(x, DI, marker='o', markersize=8, color='black', linestyle='dashed',  linewidth=2, label='DI - Random')
plt.plot(x, Acc, marker='o', markersize=8, color='gray', linewidth=2, label='AUC - Random')
plt.axhline(y=0.26, color='black', linestyle='dashed', label='DI - OT')
plt.axhline(y=0.7436, color='gray', label="AUC-OT")
plt.xticks(range(1, 10), ['5', '10', '20', '30', '35', '50', '60', '65', '70', '80'], fontsize=14)
plt.yticks(fontsize=14)
plt.xlabel('% of random edges', fontsize=15)
plt.legend(prop={'size': 15}, bbox_to_anchor=(1, 0.8))
plt.tight_layout()
plt.savefig('random_polblogs.eps')
plt.show()


*********
Knn = 3 
*********

Laplace - reg = 1
DI = 0.26515
Accuracy = 0.72129
AUC = 0.785459

Laplace - reg = 5
DI = .2728252
Accuracy = 0.72215
AUC = 0.7933122

Laplace - reg = 10
DI = 
Accuracy = 
AUC = 

*********
knn = 10 
*********

Laplace - reg = 10
DI = 0.2777466
Accuracy = 0.70145
AUC = 0.7563024

Laplace - reg = 5
DI = 0.2673
Accuracy = 0.736
AUC = 0.80436

Laplace -reg = 100
DI = 0.24832753545
Accuracy = 0.73407
AUC = 0.8025167

*******
knn = 5
*******

Laplace - reg = 50 
DI = 0.2468507
Accuracy = 0.73188
AUC = 0.793821257

Laplace - reg = 20 
DI = 0.27128387
Accuracy = 0.71700
AUC = 0.77659

Laplace - reg = 15
DI = 0.251248
Accuracy = 0.75219
AUC = 0.8159075

Laplace - reg = 10
DI = 0.243475
Accuracy = 0.76974
AUC = 0.838844

Laplace - reg = 5
DI = 0.273182
Accuracy = 0.74380
AUC = 0.0.8110876

Laplace - reg = 1
DI = 0.2873725
Accuracy = 0.69229
AUC = 0.75520286

Laplace - reg = 0.5
DI = 0.280487
Accuracy = 0.69039
AUC = 0.7470830
"""


# Laplace Polblogs
DI = [0.280487, 0.2873725, 0.273182, 0.243475, 0.27128387, 0.2468507]
DI_average = 0.26710851166
DI_std = 0.016395

Accuracy = [0.69039, 0.69229, 0.74380, 0.76974, 0.71700, 0.73188]









# Facebook
DI = [0.71467, 0.722462, 0.823175, 0.8411318, 0.784931, 0.84342443, 0.8222461, 0.7849179, 0.752890]
Acc = [0.58030, 0.55289, 0.54455, 0.5559, 0.53206, 0.54229, 0.53247, 0.52134,  0.52656]
AUC = [0.6127625, 0.5772169, 0.5821151, 0.56992940, 0.55032, 0.5680878967, 0.550203, 0.53297509, 0.5424749]
dens = [0.05734, 0.1039782, 0.127387736, 0.150741, 0.1971166, 0.220268, 0.2437866]

# Density and DI on the original graph
dens_original = 0.0224
DI_original = 0.0002

x = range(1, 10)

plt.plot(x, DI, marker='o', markersize=8, color='black', linestyle='dashed',  linewidth=2, label='DI - Random')
plt.plot(x, Acc, marker='o', markersize=8, color='gray', linewidth=2, label='AUC - Random')
plt.axhline(y=0.87839, color='black', linestyle='dashed', label='DI - OT')
plt.axhline(y=0.7436, color='gray', label="AUC-OT")
plt.xticks(range(1, 10), ['5', '10', '20', '30', '35', '50', '60', '65', '70', '80'], fontsize=14)
plt.yticks(fontsize=14)
plt.xlabel('% of random edges', fontsize=15)
plt.legend(prop={'size': 15}, bbox_to_anchor=(1, 0.55))
plt.tight_layout()
plt.savefig('random_facebook.eps')
plt.show()
